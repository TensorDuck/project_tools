""" Testing the Levenberg-Marquardt method

    The Levenberg-Marquadt method is used to solve nonlinear least squares
problems. In solving ill-posed (under- or over-determined) problems we usually
seek least-squares solutions, solutions that minimize the square of the
residual. Least-squares problems are solved with the 'normal equations' which
project the target vector onto the range of the matrix: 

    x = (A^T*A)^-1*A^T*b

    The projection operator being (A^T*A)^-1*A^T  


    In fitting real data we also want to limit the effect of the noise. This
can be done through regularization by spectral filtering. Essentially we 
replace the original system with a modified problem that is well-conditioned.

    The MC2004 implementation we have been using recently (8-1-2014) uses
truncated singular value decomposition (TSVD), where singular values below
a certain threshold are set to zero. We have been choosing the truncation
threshold in a heuristic manner thus far, so I went to the numerical 
analysis literature in order to find a quantitative method of choosing a 
solution.

    Below I have messed around with Tikhonov regularization where the 
projection operator is modified to:

    (A^T*A + gamma*D)^-1 A^T

    Where D is a diagonal matrix, usually the identity matrix or the diagonal
of the matrix A^T*A. This alters the solution from the pure least-squares
solution which minimizes,

    min||A*x - b||^2

    to include a term to minimize the size of the solution,

    min(||A*x - b|| + gamma^2*||x||^2)
    
    The parameter gamma is called the regularization parameter. When 

Also, tried using the L-curve criterion which has been written about by P.C.
Hansen. So far this test is not conclusive.

"""


import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm

from scipy import interpolate

def Levenberg(f_target,f_sim,J):
    """ Solve for new parameters with Levenberg-Marquardt method """
    pass
    #damp = np.ones(A.shape)
    #damp[(np.arange(len(A)),np.arange(len(A)))] = np.diag(A)
    #Aprime = A + gamma*damp
    #soln = np.linalg.solve(Aprime,b)


if __name__ == "__main__":

    J = np.loadtxt("Jacobian.dat")
    f_target = np.loadtxt("target_feature.dat") 
    f_sim = np.loadtxt("sim_feature.dat") 

    noise = np.random.random(J.shape)
    #J = J + noise
    #J = noise

    u,s,v = np.linalg.svd(J)

    #print s

    df = f_target - f_sim
    df /= np.linalg.norm(df)

    b = np.dot(J.T,df)
    A = np.dot(J.T,J)

    damp = np.identity(A.shape[0])
    damp[(np.arange(len(A)),np.arange(len(A)))] = np.diag(A)
    
    dampT = np.identity(A.shape[0])

    normeps =  np.linalg.norm(np.ones(A.shape[0]))

    nrm_soln = []
    nrm_resd = []
    ## Try using the L-curve test by P.C. Hansen to determine the 
    ## regularization parameter.
    #for gamma in np.arange(0.000001,100,0.001):
    Gammas = np.logspace(np.log(min(s)/1.2),np.log(2.*max(s)),num=200)
    #Gammas = np.logspace(np.log(min(s[:-20])),np.log(2.*max(s)),num=80)
    #Gammas = np.linspace(min(s)/2.,2.*max(s),num=200)
    size_perturb = []
    Xps = []
    for gamma in Gammas:
        #Tikhonov = A + gamma*dampT
        Tikhonov = A + gamma*damp

        x_soln = np.dot(np.linalg.inv(Tikhonov),b) 
        residual = np.dot(J,x_soln) - df

        nrm_soln.append(np.linalg.norm(x_soln))
        nrm_resd.append(np.linalg.norm(residual))
        size_perturb.append(np.linalg.norm(x_soln)/normeps)
        Xps.append(x_soln)
        #print np.linalg.norm(x_soln),  np.linalg.norm(residual)
        

    Covar = np.zeros((len(Xps),len(Xps)),float) 
    for i in range(len(Xps)):
        for j in range(len(Xps)):
            Covar[i,j] = np.dot(Xps[i],Xps[j])/(np.linalg.norm(Xps[i])*np.linalg.norm(Xps[j]))

    X,Y = np.meshgrid(np.log(Gammas),np.log(Gammas))
    plt.figure()
    #plt.pcolor(Covar)
    plt.pcolor(X,Y,Covar)
    plt.xlabel("$\\log{\\lambda}$")
    plt.ylabel("$\\log{\\lambda}$")
    plt.title("Covariance of solutions for different Gammas")
    plt.colorbar()


    Xps = np.array(Xps)

    #x = np.log(nrm_resd)
    #y = np.log(nrm_soln)
    #f = interpolate.interp1d(x,y)
    #g = interpolate.interp1d(x,Gammas)
    #xnew = np.linspace(min(x),max(x),10000)
    #ynew = f(xnew)
    #znew = g(xnew)
    #dy = np.diff(ynew)
    #ddy = np.diff(dy)

    #plt.figure()
    #plt.plot(znew[:-2],ddy)
    #plt.plot(znew[:-1],dy)
    #plt.xlabel("Gamma")
    #plt.ylabel("Curvature")
    #plt.ylabel("slope")
    #plt.savefig("curvature_vs_gamma.pdf")
    #plt.savefig("curvature_vs_gamma.png")

    #plt.figure()
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    ax1.loglog(nrm_resd,nrm_soln,'b') 
    #ax1.loglog(nrm_soln,nrm_resd,'b') 
    #for i in range(len(nrm_resd)):
    #    #ax1.loglog(nrm_resd[i],nrm_soln[i],'o',markeredgecolor=None,ms=5,color=cm.Blues(Gammas[i]/max(Gammas))) 
    #    ax1.loglog(nrm_soln[i],nrm_resd[i],'o',markeredgecolor=None,ms=5,color=cm.Blues(Gammas[i]/max(Gammas))) 
    ax1.set_xlabel("$||J\\delta\\epsilon - \\delta f||$")
    ax1.set_ylabel("$||\\delta\\epsilon||$")
    ax1.set_title("L-curve")

    ax2.loglog(nrm_resd,Gammas,'r')
    ax2.grid(True)
    ax2.set_ylabel("$\\lambda$")
    #plt.savefig("L_curve.pdf")
    #plt.savefig("L_curve.png")

    plt.figure()
    #plt.plot(Gammas,size_perturb,'g')
    plt.loglog(Gammas,size_perturb,'g')
    plt.xlabel("Gamma")
    plt.ylabel("$||\\delta\\epsilon||/||\\epsilon||$")

    plt.show()
