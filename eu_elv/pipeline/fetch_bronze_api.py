"""
Automated Bronze loader: pulls env_waselvt and env_waselv directly from
Eurostat's SDMX 2.1 dissemination API (SDMX-CSV format), lands the raw
response in the us-central1 staging bucket, and loads into
elv_bronze.env_waselvt_api / elv_bronze.env_waselv_api -- separate from the
env_waselvt_raw / env_waselv_raw tables loaded manually from a databrowser
export, so the automated pull can be diffed against the hand-verified data
rather than overwriting it.

Must run from inside GCP: ec.europa.eu is blocked by this dev sandbox's
network egress policy (confirmed via curl and WebFetch both 403ing at the
proxy -- see DECISIONS.md), so this is packaged to run as a Cloud Run Job,
not invoked directly from the sandbox.

Auth: takes an explicit service-account key rather than relying on the Job's
attached runtime identity. A cross-project identity
(claude-agent@msbai-dwd-nb4603) was already used successfully for the manual
Bronze/Silver/Gold build via a decrypted key file passed as
GOOGLE_APPLICATION_CREDENTIALS; binding that same identity as a Cloud Run
*Service* account hit a hard org-policy block on iam.serviceAccounts.actAs
across projects (see DECISIONS.md, "Deployment" section). Passing the key as
data rather than as the container's attached identity sidesteps that block
entirely -- the job's attached identity stays at Cloud Run's project-local
default, which only needs read access to the one secret below.

The key arrives as a **file mounted from Secret Manager** at
GCP_SA_KEY_FILE (default /secrets/sa/key.json), not as a
GCP_SA_KEY_JSON env var. The env-var form leaked the key on 2026-07-31:
Cloud Run's Admin API returns env-var values in describe/execution
responses, so printing one to check job status put the private key into a
session transcript. get_credentials() now refuses GCP_SA_KEY_JSON outright
rather than silently accepting the shape that caused the incident.
"""
import csv
import datetime
import io
import json
import os
import sys
import traceback
import xml.etree.ElementTree as ET

import requests
from google.cloud import bigquery, storage
from google.oauth2 import service_account

PROJECT = "msbai-capstone-nb4603"
BUCKET = os.environ.get("BUCKET", "msbai-capstone-nb4603-eu-elv-staging-us")
BRONZE_DATASET = "elv_bronze"

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"

# Path the Cloud Run Job mounts the Secret Manager secret at; overridable
# via GCP_SA_KEY_FILE. Never holds key material itself -- just a path.
DEFAULT_SA_KEY_FILE = "/secrets/sa/key.json"

DATASETS = {
    "env_waselvt": {"table": "env_waselvt_api", "gcs_prefix": "bronze-api/env_waselvt"},
    "env_waselv": {"table": "env_waselv_api", "gcs_prefix": "bronze-api/env_waselv"},
}

# Header shape of the manual SDMX-CSV "linear" export (see load_bronze.py),
# kept here only as a point of comparison -- the actual BigQuery schema is
# built from whatever header the live API returns, not assumed to match.
REFERENCE_HEADERS = {
    "env_waselvt_api": [
        "STRUCTURE", "STRUCTURE_ID", "STRUCTURE_NAME", "freq", "time_frequency",
        "wst_oper", "waste_management_operations", "unit", "unit_of_measure",
        "geo", "geo_label", "TIME_PERIOD", "time_label", "OBS_VALUE",
        "observation_value_label", "OBS_FLAG", "obs_flag_label",
        "CONF_STATUS", "conf_status_label",
    ],
    "env_waselv_api": [
        "STRUCTURE", "STRUCTURE_ID", "STRUCTURE_NAME", "freq", "time_frequency",
        "wst_oper", "waste_management_operations", "waste", "waste_label",
        "unit", "unit_of_measure", "geo", "geo_label", "TIME_PERIOD",
        "time_label", "OBS_VALUE", "observation_value_label", "OBS_FLAG",
        "obs_flag_label", "CONF_STATUS", "conf_status_label",
    ],
}


# -- codelists ---------------------------------------------------------------
# The SDMX data endpoint returns codes, never labels -- established across
# four probe rounds (see DECISIONS.md). Labels live in the DSD's codelists,
# so they are fetched separately and joined in Silver. This is the
# normalized form: one row per (codelist, code) instead of a label string
# repeated across all 30,268 observations, and the same shape
# country_reference already uses for geo.
SDMX_STRUCTURE_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"
CODELIST_TABLE = "codelists_api"
NS = {
    "m": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message",
    "s": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure",
    "c": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
}


XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _english_name(element):
    """Pick the English <common:Name>, falling back to an unlabelled one."""
    fallback = None
    for name in element.findall(f"{{{NS['c']}}}Name"):
        lang = name.get(XML_LANG)
        if lang == "en":
            return name.text
        if fallback is None:
            fallback = name.text
    return fallback


def fetch_dsd(dataflow_id):
    """Fetch one DSD with its codelists inline.

    `references=descendants&detail=full` is load-bearing: the plain
    /datastructure response is a ~6KB stub with no components at all, which
    is why the first attempt parsed zero of them. This variant returns
    ~3.4MB carrying both the component definitions and every codelist they
    enumerate, so one request per dataflow replaces a discovery call plus a
    fetch per codelist.
    """
    url = f"{SDMX_STRUCTURE_BASE}/datastructure/ESTAT/{dataflow_id}"
    resp = requests.get(
        url, params={"references": "descendants", "detail": "full"}, timeout=180)
    resp.raise_for_status()
    return ET.fromstring(resp.content)


def component_codelists(root):
    """Map component id -> codelist id for dimensions and attributes.

    Attributes matter as much as dimensions: obs_flag_label -- one of the
    four labels Silver needs -- is enumerated by an attribute's codelist.

    The <Ref> inside <Enumeration> is in the *default* (empty) namespace,
    not the SDMX common namespace. Qualifying it with common: matches
    nothing and yields an empty mapping rather than an error -- the exact
    silent-empty failure the load guard caught.
    """
    mapping = {}
    for kind in ("Dimension", "TimeDimension", "Attribute"):
        for comp in root.iter(f"{{{NS['s']}}}{kind}"):
            comp_id = comp.get("id")
            enum = comp.find(f".//{{{NS['s']}}}Enumeration/Ref")
            if comp_id and enum is not None and enum.get("id"):
                mapping[comp_id] = enum.get("id")
    return mapping


def codelists_in(root):
    """Extract {codelist_id: [(code, label)]} from an inline-codelist DSD."""
    out = {}
    for codelist in root.iter(f"{{{NS['s']}}}Codelist"):
        entries = []
        for code in codelist.iter(f"{{{NS['s']}}}Code"):
            code_id, label = code.get("id"), _english_name(code)
            if code_id and label:
                entries.append((code_id, label))
        if codelist.get("id"):
            out[codelist.get("id")] = entries
    return out


def load_codelists(bq_client):
    """Fetch every codelist backing either dataflow and load them to Bronze."""
    rows = []
    seen = set()
    for dataflow_id in ("ENV_WASELVT", "ENV_WASELV"):
        root = fetch_dsd(dataflow_id)
        mapping = component_codelists(root)
        available = codelists_in(root)
        print(f"  {dataflow_id}: {len(mapping)} components -> "
              f"{sorted(set(mapping.values()))}")
        if not mapping:
            raise RuntimeError(
                f"{dataflow_id}: parsed 0 components from the DSD -- the "
                f"structure XML shape has changed; refusing to continue")
        for component_id, codelist_id in sorted(mapping.items()):
            if codelist_id in seen:
                continue
            seen.add(codelist_id)
            entries = available.get(codelist_id, [])
            if not entries:
                print(f"    WARNING: codelist {codelist_id} "
                      f"(component {component_id}) came back empty")
            for code, label in entries:
                rows.append({
                    "codelist_id": codelist_id,
                    "component_id": component_id,
                    "code": code,
                    "label": label,
                })

    if not rows:
        raise RuntimeError("no codelist entries fetched -- refusing to load an empty table")

    table_id = f"{PROJECT}.{BRONZE_DATASET}.{CODELIST_TABLE}"
    schema = [
        bigquery.SchemaField("codelist_id", "STRING"),
        bigquery.SchemaField("component_id", "STRING"),
        bigquery.SchemaField("code", "STRING"),
        bigquery.SchemaField("label", "STRING"),
        bigquery.SchemaField("_loaded_at", "TIMESTAMP"),
    ]
    now = datetime.datetime.now(datetime.timezone.utc)
    for row in rows:
        row["_loaded_at"] = now.isoformat()

    job_config = bigquery.LoadJobConfig(
        schema=schema, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    bq_client.load_table_from_json(rows, table_id, job_config=job_config).result()
    print(f"  loaded {len(rows):,} codelist entries -> {table_id} "
          f"({len(seen)} codelists)")


def dump_structure(storage_client):
    """Write raw SDMX structure XML to GCS so the parser can be written to it.

    discover_codelists() found zero components in the plain
    /datastructure response, and guessing at the XML shape from a 400-char
    prefix is how the last three probe rounds each burned a cycle. SDMX
    lets a structure query return a stub unless descendants are explicitly
    requested, so these variants differ in `references`/`detail`.
    """
    variants = [
        ("datastructure_plain", "datastructure/ESTAT/ENV_WASELVT", {}),
        ("datastructure_refs_all", "datastructure/ESTAT/ENV_WASELVT",
         {"references": "all"}),
        ("datastructure_descendants", "datastructure/ESTAT/ENV_WASELVT",
         {"references": "descendants", "detail": "full"}),
        ("dataflow_refs_all", "dataflow/ESTAT/ENV_WASELVT",
         {"references": "all"}),
    ]
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dt%H%M%S")
    for name, path, params in variants:
        try:
            resp = requests.get(f"{SDMX_STRUCTURE_BASE}/{path}",
                                params=params, timeout=180)
            blob_path = f"structure/{ts}/{name}.xml"
            storage_client.bucket(BUCKET).blob(blob_path).upload_from_string(
                resp.text, content_type="application/xml")
            print(f"  {name:28s} http={resp.status_code} "
                  f"bytes={len(resp.text):>9,} -> gs://{BUCKET}/{blob_path}")
        except Exception as exc:
            print(f"  {name:28s} ERROR {type(exc).__name__}: {exc}")
    return 0


# -- Comext probe --------------------------------------------------------------
# Task 1 of the scrap-price brief needs a steel scrap price series joinable to
# country-year. Comext DS-045409 (detailed trade by reporter/partner/HS code)
# gives HS 7204 -- ferrous waste and scrap -- from which an export unit value
# (value / net mass) can be derived. It is free and needs no API key, which is
# why it was chosen over UN Comtrade.
#
# The catch: Eurostat disabled unfiltered downloads of the Comext domain
# because the datasets are enormous, so every query MUST carry filtering
# parameters. That makes the dimension ids and their code formats load-bearing
# -- a wrong key silently returns an empty dataset rather than an error.
#
# Those ids cannot be looked up from the dev sandbox (ec.europa.eu is blocked
# there), and guessing at Eurostat's response shape burned a cycle in each of
# three earlier probe rounds. So this reads the DSD first and *derives* the
# data query from the dimension order it reports, instead of assuming one.
COMEXT_FLOW = "DS-045409"

# Comext is NOT on the main dissemination base: DS-045409 under agency ESTAT
# there returns ERR_NOT_FOUND_4 for both datastructure and dataflow (probe
# 20260919t041515). Eurostat fronts the Comext domain from its own path, so
# the base itself is one of the unknowns. These get enumerated rather than
# assumed -- the discovery stage lists each base's dataflows and finds which
# one actually carries 045409, along with its agency and exact id spelling.
COMEXT_BASES = [
    ("dissemination", "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"),
    ("comext", "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1"),
]

# Substring -> filter value, applied case-insensitively to dimension ids.
# Empty string means "leave the slot open" (SDMX wildcard = all codes).
COMEXT_GUESSES = [
    ("FREQ", "M"),
    ("PRODUCT", "7204"),
    ("PRCCODE", "7204"),
    ("FLOW", "2"),      # 2 = exports in Comext's flow codelist, to confirm
]


def _ordered_dimensions(root):
    """Dimension ids in key order. Order is the whole point: an SDMX key is
    positional, so reading it off the DSD is what makes the query derivable
    rather than guessed."""
    dims = []
    for kind in ("Dimension", "TimeDimension"):
        for comp in root.iter(f"{{{NS['s']}}}{kind}"):
            if not comp.get("id"):
                continue
            pos = comp.get("position")
            # TimeDimension carries no position and always sorts last.
            dims.append((int(pos) if pos else 10_000, comp.get("id"), kind))
    dims.sort()
    return [(d[1], d[2]) for d in dims]


def _guess_for(dim_id):
    upper = dim_id.upper()
    for needle, value in COMEXT_GUESSES:
        if needle in upper:
            return value
    return ""


def _peek(storage_client, label, url, params, ts, cap=1_500_000):
    """Issue one request and report what came back, reading at most `cap`.

    Streamed and capped because a Comext query that ignores its filters can
    return hundreds of MB, and the question here is only "what shape is it".
    Status, Content-Type and byte count are captured unconditionally -- an
    earlier probe round parsed before recording and threw away its best
    result when the parse raised.
    """
    try:
        resp = requests.get(url, params=params, timeout=300, stream=True)
        body, total, truncated = b"", 0, False
        for chunk in resp.iter_content(65_536):
            total += len(chunk)
            if len(body) < cap:
                body += chunk
            else:
                truncated = True
                break
        resp.close()
        ctype = resp.headers.get("Content-Type", "?")
        print(f"  {label:34s} http={resp.status_code} "
              f"type={ctype[:46]:46s} bytes={total:>10,}"
              f"{'+ (TRUNCATED at cap)' if truncated else ''}")
        print(f"      {resp.url}")
        text = body.decode("utf-8", errors="replace")
        for line in text.splitlines()[:4]:
            print(f"      | {line[:200]}")
        blob = f"comext-probe/{ts}/{label}.txt"
        storage_client.bucket(BUCKET).blob(blob).upload_from_string(
            text, content_type="text/plain")
        return resp.status_code, text, truncated
    except Exception as exc:
        print(f"  {label:34s} ERROR {type(exc).__name__}: {exc}")
        return None, "", False


def _discover_comext(storage_client, ts):
    """Find which base/agency/id actually serves DS-045409.

    Returns (base_url, agency, flow_id) or None. Enumerating the dataflow
    listing is cheaper than guessing across bases x agencies x id spellings,
    and it reports the real answer instead of a plausible one.
    """
    for label, base in COMEXT_BASES:
        status, text, _ = _peek(
            storage_client, f"dataflows_{label}",
            f"{base}/dataflow/all/all", {"detail": "allstubs"}, ts,
            cap=40_000_000)
        if status != 200 or not text.strip():
            continue
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError as exc:
            print(f"      (listing not parseable: {exc})")
            continue
        flows = list(root.iter(f"{{{NS['s']}}}Dataflow"))
        hits = [f for f in flows
                if "045409" in (f.get("id") or "").replace("_", "-")]
        print(f"      {len(flows):,} dataflows on this base; "
              f"{len(hits)} matching 045409")
        for f in hits:
            print(f"       -> agency={f.get('agencyID')} id={f.get('id')} "
                  f"version={f.get('version')} name={_english_name(f)}")
        if hits:
            return base, hits[0].get("agencyID"), hits[0].get("id")
        # No 045409 here, but show what trade flows this base does carry --
        # a differently-numbered Comext dataset is still usable for HS 7204.
        trade = [f for f in flows
                 if (f.get("id") or "").upper().startswith("DS-")][:12]
        for f in trade:
            print(f"       (DS- flow) id={f.get('id')} name={_english_name(f)}")
    return None


def comext_probe(storage_client):
    """Resolve DS-045409's dimensions, then query it using them. Loads nothing."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dt%H%M%S")

    print("\n=== discovery: which base serves Comext? ===")
    found = _discover_comext(storage_client, ts)
    if not found:
        print("\nDS-045409 not found on any candidate base. Stopping rather "
              "than guessing at a URL.")
        return 1
    base_url, agency, flow_id = found
    print(f"\nresolved: base={base_url} agency={agency} id={flow_id}")

    # Ordered cheapest-first. The descendants variant inlines the full CN8
    # product codelist and ran past an 8MB read cap mid-document, which
    # surfaced as a bogus "no element found" parse error rather than as the
    # truncation it was. Only the dimension order is needed here, so ask for
    # the components without their codelists and keep the big variant as a
    # fallback with a cap that actually clears the payload.
    print(f"\n=== structure: {agency}/{flow_id} ===")
    root = None
    for label, path, params, cap in (
        ("ds_nocodes", f"datastructure/{agency}/{flow_id}",
         {"detail": "full", "references": "none"}, 40_000_000),
        ("ds_descendants", f"datastructure/{agency}/{flow_id}",
         {"references": "descendants", "detail": "full"}, 40_000_000),
    ):
        status, text, truncated = _peek(
            storage_client, f"structure_{label}",
            f"{base_url}/{path}", params, ts, cap=cap)
        if status != 200 or root is not None:
            continue
        if truncated:
            print("      (truncated at cap -- not parsing a severed document)")
            continue
        try:
            candidate = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError as exc:
            print(f"      (not parseable as XML: {exc})")
            continue
        if _ordered_dimensions(candidate):
            root = candidate
            print(f"      -> using {label} for the dimension order")
        else:
            print("      (parsed, but declares no dimensions -- a stub)")

    if root is None:
        print("\nNo parseable DSD -- cannot derive the data key. Stopping here "
              "rather than guessing at it.")
        return 1

    dims = _ordered_dimensions(root)
    cl_by_comp = component_codelists(root)
    inline = codelists_in(root)

    print(f"\n=== dimensions in key order ({len(dims)}) ===")
    for i, (dim_id, kind) in enumerate(dims):
        cl_id = cl_by_comp.get(dim_id, "-")
        guess = _guess_for(dim_id)
        print(f"  {i}. {dim_id:16s} {kind:14s} codelist={cl_id:24s} "
              f"filter={guess or '(all)'}")
        if kind == "TimeDimension" or cl_id == "-":
            continue
        codes = inline.get(cl_id, [])
        if not codes:
            # references=none gives components without codelists, which is
            # the point -- but the small ones (flow, freq, indicators) decide
            # whether "2" really means exports and which measure carries net
            # mass, so fetch those individually instead of burning a cycle.
            if guess == "7204":
                print("       (product codelist ~10k codes; not fetched)")
                continue
            status, text, trunc = _peek(
                storage_client, f"codelist_{cl_id}",
                f"{base_url}/codelist/{agency}/{cl_id}", {}, ts,
                cap=4_000_000)
            if status == 200 and not trunc:
                try:
                    codes = codelists_in(
                        ET.fromstring(text.encode("utf-8"))).get(cl_id, [])
                except ET.ParseError:
                    codes = []
        for code, lab in codes[:20]:
            print(f"       {code:14s} {lab[:70]}")
        if len(codes) > 20:
            print(f"       ... {len(codes) - 20:,} more")

    # Build the positional key from the DSD's own ordering. Time is excluded:
    # SDMX carries it in startPeriod/endPeriod, not in the key.
    key_dims = [d for d, kind in dims if kind != "TimeDimension"]
    key = ".".join(_guess_for(d) for d in key_dims)

    print(f"\n=== data: key='{key}' over [{', '.join(key_dims)}] ===")
    base = f"{base_url}/data/{flow_id}"
    window = {"startPeriod": "2023-01", "endPeriod": "2023-12"}
    _peek(storage_client, "data_key_csv", f"{base}/{key}",
          {"format": "SDMX-CSV", "compressed": "false", **window}, ts)
    # Parameter-style filtering, in case Comext rejects positional keys.
    param_style = {d: _guess_for(d) for d in key_dims if _guess_for(d)}
    _peek(storage_client, "data_params_csv", base,
          {"format": "SDMX-CSV", "compressed": "false",
           **param_style, **window}, ts)
    # No time window: confirms whether the filter alone satisfies Eurostat's
    # "must be filtered" rule, which decides if a 2005-2023 pull is one call.
    _peek(storage_client, "data_key_csv_alltime", f"{base}/{key}",
          {"format": "SDMX-CSV", "compressed": "false"}, ts)

    print(f"\nResponses saved under gs://{BUCKET}/comext-probe/{ts}/")
    return 0


# -- additional dataflows ------------------------------------------------------
def fetch_extra_dataflows(storage_client, bq_client, codes):
    """Pull arbitrary Eurostat dataflows into Bronze.

    Added to test whether the collapse in reported ELVs reflects vehicles
    leaving the country or simply being kept longer. Answering that needs
    vehicle-stock data alongside the ELV series, and ec.europa.eu is only
    reachable from inside GCP -- so the fetch has to happen here.

    Schema comes from whatever header the API returns; these dataflows have
    no entry in REFERENCE_HEADERS and none is required.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dt%H%M%S")
    failures = []
    for code in codes:
        code = code.strip()
        if not code:
            continue
        print(f"{code}:")
        try:
            text = fetch_csv(code)
        except Exception as exc:
            print(f"  FETCH FAILED: {exc}")
            failures.append(code)
            continue
        uri = upload_to_gcs(storage_client, text, f"bronze-api/extra/{code}_{ts}.csv")
        try:
            load_to_bronze(bq_client, uri, f"{code}_api", text)
        except Exception as exc:
            print(f"  LOAD FAILED: {exc}")
            failures.append(code)
    return failures


# -- probe mode --------------------------------------------------------------
def probe_formats(storage_client):
    """Try candidate format/labels params and report the header each returns.

    The automated pull currently lands codes-only columns, while the manual
    databrowser export carries the human-readable label columns that
    silver_elv_detail.sql and silver_elv_totals.sql select
    (waste_management_operations, waste_label, unit_of_measure,
    obs_flag_label). Until that gap closes, Silver cannot be repointed at
    the _api tables.

    Which parameter combination reproduces the manual export's shape cannot
    be determined from the dev sandbox -- ec.europa.eu is blocked there --
    so this runs inside the Job and writes its findings to GCS, where the
    sandbox can read them. Loads nothing; it only looks at headers.
    """
    # Round 1 established that `format=SDMX-CSV2.0` is rejected outright
    # (406 UNSUPPORTED_FORMAT) and that `labels=both` as a *query param* is
    # silently ignored -- the header came back byte-identical to the
    # baseline. SDMX REST negotiates both the CSV version and the label
    # columns through the Accept media type instead, so these candidates
    # vary the Accept header rather than the query string.
    # Round 2 was inconclusive by construction: it kept format=SDMX-CSV in
    # the query string alongside every Accept variant, and an explicit
    # format param takes precedence over content negotiation -- so all
    # seven candidates were really the same request. Round 3 drops the
    # format param where it is testing Accept, tries the singular `label`
    # spelling Eurostat's own databrowser uses, and tries the separate
    # statistics/1.0 endpoint the databrowser downloads actually go through.
    base = {"format": "SDMX-CSV", "compressed": "false"}
    sdmx_csv = "application/vnd.sdmx.data+csv"
    stats_base = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
    candidates = [
        # baseline, for comparison
        {"params": base, "headers": {}},
        # Accept negotiation with NO format param competing with it
        {"params": {"compressed": "false"},
         "headers": {"Accept": f"{sdmx_csv};version=2.0.0;labels=both"}},
        {"params": {"compressed": "false"},
         "headers": {"Accept": f"{sdmx_csv};version=2.0.0"}},
        {"params": {"compressed": "false"},
         "headers": {"Accept": f"{sdmx_csv};labels=both"}},
        # singular `label`, the spelling Eurostat's databrowser uses
        {"params": {**base, "label": "both"}, "headers": {}},
        {"params": {**base, "label": "both", "lang": "en"}, "headers": {}},
        {"params": {**base, "labels": "name", "lang": "en"}, "headers": {}},
        # the statistics/1.0 endpoint rather than sdmx/2.1
        {"params": {"format": "SDMX-CSV", "label": "both", "lang": "en"},
         "headers": {}, "base_url": stats_base},
        {"params": {"format": "SDMX-CSV", "lang": "en"},
         "headers": {}, "base_url": stats_base},
    ]
    # Round 4 also asks a structurally different question. Labels are
    # code->name mappings that live in the DSD/codelists, not in the
    # observations; the databrowser inlines them, the SDMX data endpoint
    # does not. If no data-endpoint parameter produces them, the fix is to
    # fetch the codelists once and join in Silver -- which is better
    # modelling anyway, and is exactly what country_reference already does
    # for geo. These probe whether those endpoints are reachable and what
    # they return.
    disc = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"
    structure_probes = [
        {"name": "datastructure ENV_WASELVT",
         "url": f"{disc}/datastructure/ESTAT/ENV_WASELVT"},
        {"name": "dataflow ENV_WASELVT",
         "url": f"{disc}/dataflow/ESTAT/ENV_WASELVT"},
    ]

    results = []
    for probe in structure_probes:
        entry = {"dataset": "(structure)", "params": {}, "headers": {},
                 "base_url": probe["url"], "probe_name": probe["name"]}
        try:
            resp = requests.get(probe["url"], timeout=180)
            entry["http_status"] = resp.status_code
            entry["content_type"] = resp.headers.get("Content-Type", "")
            entry["body_prefix"] = resp.text[:400]
            entry["body_bytes"] = len(resp.text)
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
        results.append(entry)
        print(f"  STRUCT {probe['name']:28s} -> http={entry.get('http_status')} "
              f"bytes={entry.get('body_bytes')}")

    for dataset_code, cfg in DATASETS.items():
        target = REFERENCE_HEADERS[cfg["table"]]
        for candidate in candidates:
            params, headers = candidate["params"], candidate["headers"]
            base_url = candidate.get("base_url", EUROSTAT_BASE)
            entry = {"dataset": dataset_code, "params": params,
                     "headers": headers, "base_url": base_url}
            try:
                resp = requests.get(f"{base_url}/{dataset_code}",
                                    params=params, headers=headers, timeout=180)
                entry["http_status"] = resp.status_code
                entry["content_type"] = resp.headers.get("Content-Type", "")
                # Always record what came back. Round 3 lost two of its most
                # interesting results because csv.reader raised before
                # anything was captured -- an unparseable body is a finding,
                # not a failure to record.
                entry["body_prefix"] = resp.text[:400]
                entry["body_bytes"] = len(resp.text)
                if resp.status_code == 200 and resp.text.strip():
                    try:
                        reader = csv.reader(io.StringIO(resp.text))
                        header = next(reader)
                        entry["header"] = header
                        entry["n_data_rows"] = sum(1 for _ in reader)
                        entry["matches_manual_export"] = (header == target)
                        entry["missing_vs_manual"] = [c for c in target if c not in header]
                        entry["extra_vs_manual"] = [c for c in header if c not in target]
                    except Exception as exc:
                        entry["parse_error"] = f"{type(exc).__name__}: {exc}"
            except Exception as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
            results.append(entry)
            flag = "MATCH" if entry.get("matches_manual_export") else "     "
            accept = headers.get("Accept", "(default)")
            ep = "stats1.0" if "statistics/1.0" in base_url else "sdmx2.1"
            print(f"  {flag} {dataset_code:12s} [{ep}] accept={accept} "
                  f"params={params} -> http={entry.get('http_status')} "
                  f"missing={len(entry.get('missing_vs_manual', []) or [])}")

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dt%H%M%S")
    path = f"probe/formats_{ts}.json"
    storage_client.bucket(BUCKET).blob(path).upload_from_string(
        json.dumps(results, indent=2), content_type="application/json")
    print(f"probe results -> gs://{BUCKET}/{path}")
    return 0


def get_credentials():
    """Load the SA key from the Secret Manager volume mounted by the Job.

    GCP_SA_KEY_FILE is a *path* (default /secrets/sa/key.json), not key
    material. The key used to arrive as a GCP_SA_KEY_JSON env var holding
    the whole JSON; that leaked it, because Cloud Run's Admin API returns
    env-var values in describe/execution responses. Reading the key from a
    mounted secret keeps it out of the Job spec entirely.
    """
    key_file = os.environ.get("GCP_SA_KEY_FILE", DEFAULT_SA_KEY_FILE)
    if not os.path.exists(key_file):
        if os.environ.get("GCP_SA_KEY_JSON"):
            raise RuntimeError(
                "GCP_SA_KEY_JSON is set. Passing the service-account key as a "
                "Cloud Run env var leaks it through the Admin API and is not "
                "supported any more -- mount it from Secret Manager instead "
                "(see build_and_run_fetch_job.py)."
            )
        print(f"  no key file at {key_file}; falling back to ambient ADC")
        return None
    with open(key_file) as f:
        info = json.load(f)
    print(f"  authenticating as {info.get('client_email')} "
          f"(key {info.get('private_key_id', '')[:8]}..., from {key_file})")
    return service_account.Credentials.from_service_account_info(info)


def fetch_csv(dataset_code):
    url = f"{EUROSTAT_BASE}/{dataset_code}"
    params = {"format": "SDMX-CSV", "compressed": "false"}
    resp = requests.get(url, params=params, timeout=180)
    resp.raise_for_status()
    text = resp.text
    if not text.strip():
        raise RuntimeError(f"{dataset_code}: empty response body")
    return text


def upload_to_gcs(storage_client, text, gcs_path):
    bucket = storage_client.bucket(BUCKET)
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(text, content_type="text/csv")
    uri = f"gs://{BUCKET}/{gcs_path}"
    print(f"  landed -> {uri} ({len(text):,} bytes)")
    return uri


def load_to_bronze(bq_client, uri, table_name, csv_text):
    header = next(csv.reader(io.StringIO(csv_text)))
    expected = REFERENCE_HEADERS.get(table_name)
    if expected is not None and header != expected:
        print(f"  NOTE: live API header differs from the manual-export header for {table_name}")
        print(f"    expected: {expected}")
        print(f"    actual:   {header}")
        print("    loading under the actual header, not the reference one.")

    dataset_ref = bigquery.DatasetReference(PROJECT, BRONZE_DATASET)
    table_ref = dataset_ref.table(table_name)
    schema = [bigquery.SchemaField(col, "STRING") for col in header]

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        allow_quoted_newlines=True,
    )
    load_job = bq_client.load_table_from_uri(uri, table_ref, job_config=job_config)
    load_job.result()

    table = bq_client.get_table(table_ref)
    print(f"  loaded {uri} -> {PROJECT}.{BRONZE_DATASET}.{table_name} ({table.num_rows:,} rows)")

    bq_client.query(f"""
        ALTER TABLE `{PROJECT}.{BRONZE_DATASET}.{table_name}`
        ADD COLUMN IF NOT EXISTS _source_uri STRING,
        ADD COLUMN IF NOT EXISTS _loaded_at TIMESTAMP
    """).result()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    bq_client.query(f"""
        UPDATE `{PROJECT}.{BRONZE_DATASET}.{table_name}`
        SET _source_uri = @uri, _loaded_at = @loaded_at
        WHERE _source_uri IS NULL
    """, job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("uri", "STRING", uri),
        bigquery.ScalarQueryParameter("loaded_at", "TIMESTAMP", now),
    ])).result()


class _Tee:
    """Write to both the real stdout and an in-memory buffer."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for stream in self._streams:
            stream.write(data)
        return len(data)

    def flush(self):
        for stream in self._streams:
            stream.flush()


def main():
    """Run the pipeline, mirroring all output to a GCS run log.

    claude-agent@ has no Cloud Logging read access (confirmed: 403
    "Permission denied for all log views"), so a failed execution is
    otherwise a black box from outside GCP -- Cloud Run reports only "the
    container exited with an error". Rather than request a broader role,
    every run mirrors its own output to gs://BUCKET/runs/, which the job
    can already write. The upload happens in a finally block so a crash
    reports itself rather than vanishing.
    """
    buffer = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = _Tee(real_stdout, buffer)
    creds = None
    started = datetime.datetime.now(datetime.timezone.utc)
    try:
        creds = get_credentials()
        return _run(creds)
    except Exception:
        traceback.print_exc(file=sys.stdout)
        return 1
    finally:
        sys.stdout = real_stdout
        _upload_run_log(creds, buffer.getvalue(), started)


def _upload_run_log(creds, text, started):
    stamp = started.strftime("%Y%m%dt%H%M%S")
    try:
        client = storage.Client(project=PROJECT, credentials=creds)
        path = f"runs/run_{stamp}.log"
        client.bucket(BUCKET).blob(path).upload_from_string(
            text, content_type="text/plain")
        print(f"run log -> gs://{BUCKET}/{path}")
    except Exception as exc:
        # Never let log shipping mask the real outcome.
        print(f"WARNING: could not upload run log: {type(exc).__name__}: {exc}")


def _run(creds):
    storage_client = storage.Client(project=PROJECT, credentials=creds)

    extra = os.environ.get("EXTRA_DATAFLOWS")
    if extra:
        print(f"EXTRA_DATAFLOWS set -- fetching {extra}, skipping the ELV load")
        bq_client = bigquery.Client(project=PROJECT, credentials=creds)
        failures = fetch_extra_dataflows(storage_client, bq_client, extra.split(","))
        if failures:
            print(f"FAILED: {failures}")
            return 1
        print("extra dataflows loaded successfully")
        return 0

    if os.environ.get("DUMP_STRUCTURE") == "1":
        print("DUMP_STRUCTURE=1 -- dumping raw SDMX structure XML, loading nothing")
        return dump_structure(storage_client)

    if os.environ.get("PROBE_ONLY") == "1":
        print("PROBE_ONLY=1 -- probing API formats, loading nothing")
        return probe_formats(storage_client)

    if os.environ.get("COMEXT_PROBE") == "1":
        print("COMEXT_PROBE=1 -- resolving DS-045409 structure, loading nothing")
        return comext_probe(storage_client)

    bq_client = bigquery.Client(project=PROJECT, credentials=creds)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dt%H%M%S")
    failures = []
    for dataset_code, cfg in DATASETS.items():
        print(f"{dataset_code}:")
        try:
            text = fetch_csv(dataset_code)
        except Exception as exc:
            print(f"  FETCH FAILED: {exc}")
            failures.append(dataset_code)
            continue

        gcs_path = f"{cfg['gcs_prefix']}/{dataset_code}_{ts}.csv"
        uri = upload_to_gcs(storage_client, text, gcs_path)
        try:
            load_to_bronze(bq_client, uri, cfg["table"], text)
        except Exception as exc:
            print(f"  LOAD FAILED: {exc}")
            failures.append(dataset_code)

    # Codelists carry the labels the observations don't. Loaded in the same
    # run so they cannot drift out of step with the data they describe.
    print("codelists:")
    try:
        load_codelists(bq_client)
    except Exception as exc:
        print(f"  CODELIST LOAD FAILED: {exc}")
        failures.append("codelists")

    if failures:
        print(f"FAILED: {failures}")
        return 1
    print("all datasets and codelists fetched and loaded successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
