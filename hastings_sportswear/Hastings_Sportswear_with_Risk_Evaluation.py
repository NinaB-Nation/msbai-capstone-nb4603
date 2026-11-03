# HASTING SPORTSWEAR WITH RISK EVALUATION
import math
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats
import seaborn as sns




def get_confidence_interval_for_mean(profits):
    # Returns the 95% CI
    mu_p = np.mean(profits)
    sigma_p = np.std(profits)
    coef = 1.96
    n = len(profits)

    mse=sigma_p/math.sqrt(n)
    CI_LB=mu_p - coef*mse
    CI_UB=mu_p + coef*mse

    return (CI_LB,CI_UB)



def get_sample_prob_minx(profits,x):
    success = [p for p in profits if p >= x]
    fraction = len(success)/len(profits)
    return fraction
    


def main():


    n_trials = 10000 # number of trials to run
    p = 110    # wholesale price
    c_percent = 0.75 
    s_percent = 0.08
    
    c = p*c_percent    # cost per unit
    s = p*s_percent    # salvage value

    # Demand: Parameters of the normal distribution
    mu = 1017
    sigma = 2*194

    # Next command sets the seed to generate the same sequence of pseudorandom 
    # numbers every time you run the script and hence it allows to replicate reults
    # In this case, it also enforces different order quantities q to face the 
    # same sequence of demand 
    # The argument is an arbitrary integer
    np.random.seed(1000)

    # Generate a list of random draws from the (normal) demand random variable
    demand_samples = stats.norm.rvs(loc=mu, scale=sigma, size=n_trials)
      
    # The negative demands are replaced by 0
    demand_samples=[max(d,0) for d in demand_samples]
   
    
    # The following lines (commented) plot the histogram of the truncated demand
    # plt.hist(demand_samples,bins=300,density=True)
    # plt.title('Demand')
    # plt.show()

    # Map the demand onto profits by creating a list of profits, 
    # each of them corresponding to a particular demand realization contained 
    # in the list demand_samples
    q = 1017   # Order quantity
    profits_1017 = [p*min(q,d) - c*q + s*max(q-d,0) for d in demand_samples]


    q = 814   # Order quantity
    profits_814 = [p*min(q,d) - c*q + s*max(q-d,0) for d in demand_samples]


    q = 1220   # Order quantity
    profits_1220 = [p*min(q,d) - c*q + s*max(q-d,0) for d in demand_samples]


    q = 782   # Order quantity: newsvendor (profit-maximizing) solution Q*
    profits_782 = [p*min(q,d) - c*q + s*max(q-d,0) for d in demand_samples]


    # Create an overlay chart of profits (overlap of cumulative density function) 
    sns.kdeplot(data=profits_1017, cumulative=True, label = "@ q=1017")
    sns.kdeplot(data=profits_814, cumulative=True, label = "@ q=814")
    sns.kdeplot(data=profits_1220, cumulative=True, label = "@ q=1220")
    sns.kdeplot(data=profits_782, cumulative=True, label = "@ q=782 (Q*)")

    plt.legend(loc='upper left');
    plt.ylim(0.0,1.05)
    plt.grid(True)
    plt.title('Profit: Overlay Chart')
    plt.savefig('Profit_Overlay_Chart.pdf', format='pdf')
    plt.savefig('Profit_Overlay_Chart.png', dpi=150)
    plt.show()

    # Report results
    print('\n========================================')
    print('Performance of order quantity q=1017:')
    # Profit: 95% CI for the mean
    conf_int=get_confidence_interval_for_mean(profits_1017)
    print('95% CI for Profit: ({:.2f}, {:.2f})'.format(conf_int[0], conf_int[1]))
    # Probab. of making a positive cashflow
    prob_0 = get_sample_prob_minx(profits_1017,0)
    print('P(Profit >= 0)= {:.3f}'.format(prob_0))
    prob_minus10000 = get_sample_prob_minx(profits_1017,-10000)
    print('P(Profit < -10000)= {:.3f}'.format(1-prob_minus10000))


    print('\n========================================')
    print('Performance of order quantity q=814:')
    # Profit: 95% CI for the mean
    conf_int=get_confidence_interval_for_mean(profits_814)
    print('95% CI for Profit: ({:.2f}, {:.2f})'.format(conf_int[0], conf_int[1]))
    # Probab. of making a positive cashflow
    prob_0 = get_sample_prob_minx(profits_814,0)
    print('P(Profit >= 0)= {:.3f}'.format(prob_0))
    prob_minus10000 = get_sample_prob_minx(profits_814,-10000)
    print('P(Profit < -10000)= {:.3f}'.format(1-prob_minus10000))


    print('\n========================================')
    print('Performance of order quantity q=1220:')
    # Profit: 95% CI for the mean
    conf_int=get_confidence_interval_for_mean(profits_1220)
    print('95% CI for Profit: ({:.2f}, {:.2f})'.format(conf_int[0], conf_int[1]))
    # Probab. of making a positive cashflow
    prob_0 = get_sample_prob_minx(profits_1220,0)
    print('P(Profit >= 0)= {:.3f}'.format(prob_0))
    prob_minus10000 = get_sample_prob_minx(profits_1220,-10000)
    print('P(Profit < -10000)= {:.3f}'.format(1-prob_minus10000))


    print('\n========================================')
    print('Performance of order quantity q=782 (newsvendor Q*):')
    # Profit: 95% CI for the mean
    conf_int=get_confidence_interval_for_mean(profits_782)
    print('95% CI for Profit: ({:.2f}, {:.2f})'.format(conf_int[0], conf_int[1]))
    # Probab. of making a positive cashflow
    prob_0 = get_sample_prob_minx(profits_782,0)
    print('P(Profit >= 0)= {:.3f}'.format(prob_0))
    prob_minus10000 = get_sample_prob_minx(profits_782,-10000)
    print('P(Profit < -10000)= {:.3f}'.format(1-prob_minus10000))

    print('\n========================================')

    return # End of the main function


# Call the main() function when running the script
if __name__ == "__main__":
    main()


