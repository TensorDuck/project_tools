""" Submodule to calculate the simulation phi values

Description:

    Submodule to calculate the energetic perturbation from each
mutation and the results DeltaDetla G's for simulation.


References:

(1) Matysiak, S.; Clementi, C. Optimal Combination of Theory and Experiment for
the Characterization of the Protein Folding Landscape of S6: How Far Can a
Minimalist model Go? J. Mol. Biol. 2004, 343, 235-248.
"""

import os
import argparse
import time
import numpy as np

import mdtraj as md

import model_builder as mdb

from mutatepdbs import get_core_mutations, get_scanning_mutations,  get_exp_ddG

global GAS_CONSTANT_KJ_MOL
GAS_CONSTANT_KJ_MOL = 0.0083144621

def get_state_bounds():
    """ Bounds for each state. Bounds are bin edges along Q. """
    if os.path.exists("state_bounds.txt"):
        statefile = open("state_bounds.txt","r").readlines()
    else:
        print "ERROR!"
        print "  Please create state_bounds.txt"
        print "  With the boundaries of each state along Q"
        print "  Exiting"
        raise SystemExit
    
    state_bounds = []
    state_labels = []
    for line in statefile:
        info = line.split()
        state_bounds.append(float(info[1]))
        state_bounds.append(float(info[2]))
        state_labels.append(info[0])
    
    return state_bounds,state_labels

def get_states_Vij(model,bounds):
    """ Load trajectory, state indicators, and contact energy """

    traj = md.load("traj.xtc",top="Native.pdb")     ## Loading from file takes most time.
    rij = md.compute_distances(traj,model.contacts-np.ones(model.contacts.shape),periodic=False)
    Q = np.loadtxt("Q.dat") ## To Do: Generalize to different reaction coordinates

    state_indicator = np.zeros(len(Q),int)
    ## Assign every frame a state label. State indicator is integer 1-N for N states.
    for state_num in range(len(bounds)-1):
        instate = (Q > bounds[state_num]).astype(int)*(Q <= bounds[state_num+1]).astype(int)
        state_indicator[instate == 1] = state_num+1
    if any(state_indicator == 0):
        num_not_assign = sum((state_indicator == 0).astype(int))
        print "  Warning! %d frames were not assigned out of %d total frames!" % (num_not_assign,len(Q))
    ## Boolean arrays that indicate which state each frame is in.
    ## States are defined by their boundaries along coordinate Q.
    U  = ((Q > bounds[1]).astype(int)*(Q < bounds[2]).astype(int)).astype(bool)
    TS = ((Q > bounds[3]).astype(int)*(Q < bounds[4]).astype(int)).astype(bool)
    N  = ((Q > bounds[5]).astype(int)*(Q < bounds[6]).astype(int)).astype(bool)
    Nframes  = float(sum(N.astype(int)))
    Uframes  = float(sum(U.astype(int)))
    TSframes = float(sum(TS.astype(int)))

    Vij = model.calculate_contact_potential(rij)

    return traj,U,TS,N,Uframes,TSframes,Nframes,Vij

def get_target_feature(model):
    """ Get target features """
    name = model.subdir
    iteration = model.Mut_iteration

    cwd = os.getcwd()
    os.chdir("%s/mutants" % name)
    target_feature, target_feature_err = get_exp_ddG()
    os.chdir(cwd)

    return target_feature, target_feature_err

def calculate_average_Jacobian(model,scanning_only=False,scanfij=0.5,saveas="Q_phi.dat"):
    """ Calculate the average feature vector (ddG's) and Jacobian """
    
    name = model.subdir
    iteration = model.Mut_iteration

    cwd = os.getcwd()
    sub = "%s/%s/Mut_%d" % (cwd,name,iteration)
    os.chdir("%s/mutants" % name)
    ## Get list of mutations and fraction of native contacts deleted for 
    ## each mutation.
    mutants_core = get_core_mutations()
    Fij_core, Fij_pairs_core, Fij_conts_core = get_mutant_fij(model,mutants_core)
    mutants_scanning = get_scanning_mutations()
    Fij_scanning, Fij_pairs_scanning, Fij_conts_scanning = get_mutant_fij_scanning(model,mutants_scanning,fij=scanfij)

    if scanning_only:
        mutants = mutants_scanning
        Fij = Fij_scanning
        Fij_pairs = Fij_pairs_scanning
        Fij_conts = Fij_conts_scanning
        saveas = "scan_%.2f.dat" % scanfij
    else:
        mutants = mutants_core + mutants_scanning
        Fij = Fij_core + Fij_scanning
        Fij_pairs = Fij_pairs_core + Fij_pairs_scanning
        Fij_conts = Fij_conts_core + Fij_conts_scanning

    os.chdir(sub)

    temperatures = [ x.split('_')[0] for x in open("T_array_last.txt","r").readlines() ] 
    directories = [ x.rstrip("\n") for x in open("T_array_last.txt","r").readlines() ] 

    bounds, state_labels = get_state_bounds()
    bounds = [0] + bounds + [model.n_contacts]

    ## Loop over temperatures in Mut subdir. Calculate ddG vector and 
    ## Jacobian for each directory indpendently then save. Save the average
    ## feature vector and Jacobian in the Mut/newton directory.
    sim_feature_all = []
    Jacobian_all = []
    lasttime = time.time()
    for n in range(len(directories)):
        T = temperatures[n]
        dir = directories[n]
        beta = 1./(GAS_CONSTANT_KJ_MOL*float(T))
        print "  Calculating Jacobian for Mut_%d/%s" % (model.Mut_iteration,dir)
        os.chdir(dir)
        sim_feature, Jacobian = compute_Jacobian_for_directory(model,beta,mutants,Fij,Fij_pairs,Fij_conts,bounds,state_labels,saveas=saveas)
        sim_feature_all.append(sim_feature)
        Jacobian_all.append(Jacobian)
        os.chdir("..")
        thistime = time.time()
        timediff = thistime - lasttime
        lasttime = thistime
        print "  calculation took %.2f seconds = %.2f minutes" % (timediff,timediff/60.)

    sim_feature_all = np.array(sim_feature_all)
    Jacobian_all = np.array(Jacobian_all)

    ## Take avg. and use standard deviation as error bars.
    sim_feature_avg = sum(sim_feature_all)/float(len(directories))
    sim_feature_err = np.std(sim_feature_all,axis=0)
    Jacobian_avg = sum(Jacobian_all)/float(len(directories))
    Jacobian_err = np.std(Jacobian_all,axis=0)

    os.chdir(cwd)

    return sim_feature_avg, sim_feature_err, Jacobian_avg, Jacobian_err

def compute_Jacobian_for_directory(model,beta,mutants,Fij,Fij_pairs,Fij_conts,bounds,state_labels,saveas="Q_phi.dat"):
    """ Calculates the feature vector (ddG's) and Jacobian for one directory """
    ## Get trajectory, state indicators, contact energy
    traj,U,TS,N,Uframes,TSframes,Nframes,Vij = get_states_Vij(model,bounds)

    ## Avg. contact energy for each state.
    Vij_U  = sum(Vij[U,:])/Uframes
    Vij_TS = sum(Vij[TS,:])/TSframes
    Vij_N  = sum(Vij[N,:])/Nframes

    ## Compute deltaG for each state. Then DeltaDelta G with respect to the
    ## first state (assumed to be the unfolded/denatured state).
    ## Units of kT.
    dG = [[],[],[]]
    ddG = [[],[]]
    phi = []

    ## Initialize Jacobian
    Jacobian = np.zeros((2*len(mutants),model.n_contacts),float)
    sim_feature = np.zeros(2*len(mutants),float)

    for k in range(len(mutants)):
        mut = mutants[k]
        print "    row %d   mutant %s" % (k,mut)
        ## Compute energy perturbation
        #print Fij_conts[k]
        #continue
        tempVij = -np.array(Fij[k])*Vij[:,np.array(Fij_conts[k])]
        dHk = sum(tempVij.T)
        np.savetxt("dH_%s.dat" % mut,dHk)

        ## Free energy perturbation formula. Equation (4) in reference (1).
        dG_U  = -np.log(np.sum(np.exp(-beta*dHk[U]))/Uframes)
        dG_TS = -np.log(np.sum(np.exp(-beta*dHk[TS]))/TSframes)
        dG_N  = -np.log(np.sum(np.exp(-beta*dHk[N]))/Nframes)

        ## DeltaDeltaG's. Equations (5) in reference (1).
        ddG_stab = (dG_N - dG_U)
        ddG_dagg = (dG_TS - dG_U)

        ## Phi-value
        phi_value = ddG_dagg/ddG_stab

        dG[0].append(dG_U)
        dG[1].append(dG_TS)
        dG[2].append(dG_N)
        ddG[0].append(ddG_dagg)
        ddG[1].append(ddG_stab)
        phi.append(phi_value)

        ## Thermal averages for matrix equation (9).
        expdHk_U  = sum(np.exp(-beta*dHk[U]))/Uframes
        expdHk_TS = sum(np.exp(-beta*dHk[TS]))/TSframes
        expdHk_N  = sum(np.exp(-beta*dHk[N]))/Nframes

        Vij_expdHk_U  = sum((Vij[U,:].T*np.exp(-beta*dHk[U])).T)/Uframes
        Vij_expdHk_TS = sum((Vij[TS,:].T*np.exp(-beta*dHk[TS])).T)/TSframes
        Vij_expdHk_N  = sum((Vij[N,:].T*np.exp(-beta*dHk[N])).T)/Nframes

        ## Compute all columns with Fij_k zero.
        Jacobian[k,:] = -beta*((Vij_TS - Vij_U) -  ((Vij_expdHk_TS/expdHk_TS) - (Vij_expdHk_U/expdHk_U)))
        Jacobian[k + len(mutants),:] = -beta*((Vij_N - Vij_U)  -  ((Vij_expdHk_N/expdHk_N) - (Vij_expdHk_U/expdHk_U)))

        ## Replace columns for which Fij_k is not zero.
        Jacobian[k,Fij_conts[k]] = -beta*((Vij_TS[Fij_conts[k]] - Vij_U[Fij_conts[k]])  - \
            (1. - Fij[k])*((Vij_expdHk_TS[Fij_conts[k]]/expdHk_TS) - \
                           (Vij_expdHk_U[Fij_conts[k]]/expdHk_U)))

        Jacobian[k + len(mutants),Fij_conts[k]] = -beta*((Vij_N[Fij_conts[k]] - Vij_U[Fij_conts[k]])  -  \
            (1. - Fij[k])*((Vij_expdHk_N[Fij_conts[k]]/expdHk_N)   - \
                          (Vij_expdHk_U[Fij_conts[k]]/expdHk_U)))

        ## return feature vector and Jacobian
        sim_feature[k] = ddG_dagg
        sim_feature[k + len(mutants)] = ddG_stab

    if not os.path.exists("mut"):
        os.mkdir("mut")
    np.savetxt("mut/Jacobian.dat",Jacobian)
    np.savetxt("mut/sim_feature.dat",sim_feature)
    save_phi_values(mutants,"Q",state_labels,dG,ddG,phi,saveas=saveas)

    return sim_feature, Jacobian

def get_mutant_fij(model,mutants):
    """ Load in the fraction of contact loss for each mutation.

    Description:

        Since the fraction of contacts lost matrix f^k_ij is sparse only load
    in the of nonzero elements and their indices. Determine the contact indices
    for nonzero entries.
    """
    Fij_pairs = []
    Fij_conts = []
    Fij = []
    for mut in mutants:
        fij_temp = model.Qref*np.loadtxt("fij_"+mut+".dat")
        indices = np.nonzero(fij_temp)
        Fij.append(fij_temp[indices])
        temppairs = []
        tempconts = []
        tempfij = []
        for i in range(len(indices[0])):
            for j in range(model.n_contacts):
                if (model.contacts[j,0] == (indices[0][i]+1)) and (model.contacts[j,1] == (indices[1][i]+1)):
                    contact_num = j
                    temppairs.append([indices[0][i],indices[1][i]])
                    tempconts.append(contact_num)
                    tempfij.append(fij_temp[indices[0][i],indices[1][i]])
                    break
                else:
                    continue
        Fij_conts.append(np.array(tempconts))
        Fij_pairs.append(temppairs)
    return Fij, Fij_pairs, Fij_conts

def get_mutant_fij_scanning(model, mutants, fij=0.5):
    """Estimate the local contact fraction loss for scanning mutations.
    
    The ddGs for scanning mutations could be affected by a multiplicity of factors that exceed the mere contacts lost (e.g. effect 
    of solvent, interaction with helix dipole, interaction with charged residues, loss of hydrogen bonds, among others). As a result,
    the exact determination varies according to which factor(s) weigh the most. Given that this is a coarse-grained model, as a 
    first approach we will estimate an average value of fij = 0.5. This is as said before arbitrary, but should give us an estimate
    of how the local epsilons vary according to the value of the ddGs involved.

    Also, on a first approach only the [i, i+4] contacts will be affected by the said value of fij.

    """
    
    Fij_pairs = []
    Fij_conts = []
    Fij = []

    for mut in mutants:
        # For the time being only keeping i, i+4
        mut_res_number = int("".join(list(mut)[1:-1]))
        Fij.append(fij)
        temppairs = []
        tempconts = []
        tempfij = []

        for j in range(model.n_contacts):
            if (model.contacts[j,0] == mut_res_number) and (model.contacts[j,1] == (mut_res_number+4)):
                contact_num = j
                temppairs.append([mut_res_number-1,mut_res_number+3])  #i, i+4
                tempconts.append(contact_num)
                tempfij.append(fij)
                break
            else:
                continue

        Fij_conts.append(np.array(tempconts))
        Fij_pairs.append(temppairs)
    return Fij, Fij_pairs, Fij_conts


def get_Qij(model,r,sig,deltas,interaction_nums):
    """ Calculates the normalized interaction betwen nonbonded pairs.

        Might use to generalize for different types of contacts.
    """
    print "  Calculating Qij..."
    qij = model.nonbond_interaction(r,sig,deltas)
    return qij

def save_phi_values(mutants,coord,state_labels,dG,ddG,phi,saveas="Q_phi.dat"):
    """ Save the calculated dG, ddG, and phi values for states"""

    header_string = "# mut" 
    for i in range(len(state_labels)):
        header_string += "     dG_"+state_labels[i]+"(kT)"
    header_string += "    "
    for i in range(1,len(state_labels)):
        header_string += " ddG_"+state_labels[i]+"-"+state_labels[0]+"(kT)"
    for i in range(1,len(state_labels)-1):
        header_string += "   Phi_"+state_labels[i]+"/"+state_labels[-1]

    data_string = ''
    for j in range(len(mutants)):
        line = "%6s"%mutants[j]
        for i in range(len(dG)):
            line += "  %10.5f " % dG[i][j]
        for i in range(len(ddG)):
            line += "  %10.5f " % ddG[i][j]
        line += "  %10.5f  " % phi[j]
        data_string += line+"\n"
    print "ddG and Phi values:"
    print header_string
    print data_string

    if not os.path.exists("phi"):
        os.mkdir("phi")
    outputfile = open("phi/%s" % saveas,"w")
    outputfile.write(header_string+"\n"+data_string)
    outputfile.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Calculate .')
    parser.add_argument('--name', type=str, required=True, help='name.')
    parser.add_argument('--iteration', type=int, required=True, help='iteration.')
    #parser.add_argument('--savein', type=str, required=True, help='Directory to save in.')
    parser.add_argument('--scanningfij', type=float, default=0.5, help='Scanning fij.')
    args = parser.parse_args()
    
    name = args.name
    iteration= args.iteration

    T = open("%s/Mut_%d/T_array_last.txt" % (name,iteration),"r").readlines()[0].rstrip("\n")
    epsilons = np.loadtxt("%s/Mut_%d/%s/BeadBead.dat" % (name,iteration,T),usecols=(6,),dtype=float)

    model = mdb.check_inputs.load_model(name)
    model.Mut_iteration = iteration
    model.contact_epsilons = epsilons

    target_feature, target_feature_err = get_target_feature(model)

    cwd = os.getcwd()
    sub = "%s/%s/Mut_%d" % (cwd,name,iteration)
    os.chdir("%s/mutants" % name)
    ## Get list of mutations and fraction of native contacts deleted for 
    ## each mutation.
    mutants_core = get_core_mutations()
    Fij_core, Fij_pairs_core, Fij_conts_core = get_mutant_fij(model,mutants_core)
    mutants_scanning = get_scanning_mutations()
    Fij_scanning, Fij_pairs_scanning, Fij_conts_scanning = get_mutant_fij_scanning(model,mutants_scanning,fij=0.5)

    scanning_only = False
    if scanning_only:
        mutants = mutants_scanning
        Fij = Fij_scanning
        Fij_pairs = Fij_pairs_scanning
        Fij_conts = Fij_conts_scanning
        saveas = "scan_%.2f.dat" % scanfij
    else:
        mutants = mutants_core + mutants_scanning
        Fij = Fij_core + Fij_scanning
        Fij_pairs = Fij_pairs_core + Fij_pairs_scanning
        Fij_conts = Fij_conts_core + Fij_conts_scanning

    os.chdir(sub)

    temperatures = [ x.split('_')[0] for x in open("T_array_last.txt","r").readlines() ] 
    directories = [ x.rstrip("\n") for x in open("T_array_last.txt","r").readlines() ] 

    bounds, state_labels = get_state_bounds()
    bounds = [0] + bounds + [model.n_contacts]

    sim_feature_all = []
    Jacobian_all = []
    lasttime = time.time()
    for n in [0]:
        T = temperatures[n]
        dir = directories[n]
        beta = 1./(GAS_CONSTANT_KJ_MOL*float(T))
        print "  Testing for Mut_%d/%s" % (model.Mut_iteration,dir)
        os.chdir(dir)
        sim_feature, Jacobian = compute_Jacobian_for_directory(model,beta,mutants,Fij,Fij_pairs,Fij_conts,bounds,state_labels)

        #traj,U,TS,N,Uframes,TSframes,Nframes,Vij = get_states_Vij(model,bounds)
        #for k in range(5):
        #    mut = mutants[k]
        #    print "    row %d   mutant %s" % (k,mut)
        #    tempVij = -np.array(Fij[k])*Vij[:,np.array(Fij_conts[k])]
        #    dHk = sum(tempVij.T)
        #    #np.savetxt("dH_%s.dat" % mut,dHk)
        #    np.savetxt("dH_%s_new.dat" % mut,dHk)

        os.chdir("..")

    os.chdir(cwd)

    sim_feature_err = np.zeros(len(sim_feature))
    Jacobian_err = np.zeros(Jacobian.shape)
    method = "newton_test"
    if not os.path.exists("%s/Mut_%d/%s" % (name,iteration,method)):
        os.mkdir("%s/Mut_%d/%s" % (name,iteration,method))
    print "  Saving feature vector and Jacobian in %s/Mut_%d/%s" % (name,iteration,method)
    np.savetxt("%s/Mut_%d/%s/target_feature.dat" % (name,iteration,method), target_feature)
    np.savetxt("%s/Mut_%d/%s/target_feature_err.dat" % (name,iteration,method), target_feature_err)
    np.savetxt("%s/Mut_%d/%s/sim_feature.dat" % (name,iteration,method), sim_feature)
    np.savetxt("%s/Mut_%d/%s/sim_feature_err.dat" % (name,iteration,method), sim_feature_err)
    np.savetxt("%s/Mut_%d/%s/Jacobian.dat" % (name,iteration,method), Jacobian)
    np.savetxt("%s/Mut_%d/%s/Jacobian_err.dat" % (name,iteration,method) ,Jacobian_err)
