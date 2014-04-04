import numpy as np
import os

import mdtraj as md
import model_builder.models as models
import model_builder.systems as systems


'''
Alexander Kluber

Seed script to figure out how to calculate Phi-values.
'''

global GAS_CONSTANT_KJ_MOL
GAS_CONSTANT_KJ_MOL = 0.0083144621


def get_state_bounds(path,coord):
    ''' Get bounds for each state for specified coordinate. Return a list of boolean
        arrays that specifies if each frame is in the given state or not.'''
    print path+"/"+coord+"_states.txt"
    print open(path+"/"+coord+"_states.txt","r").read()

    statefile = open(path+"/"+coord+"_states.txt","r").readlines()[1:]
    bounds = []
    for line in statefile:
        bounds.append([line.split()[0],float(line.split()[1]),float(line.split()[2]),float(line.split()[3])])

    if coord in ["Q","Qnh","Qh"]:
        data = np.loadtxt(path+"/"+coord+"prob.dat")
        data /= max(data)
    elif coord == "Nh":
        data = np.loadtxt(path+"/Nh.dat")
    elif coord == "Rg":
        dummy,data = np.loadtxt(path+"/radius_cropped.xvg",unpack=True)
    elif coord == "rmsd":
        dummy,data = np.loadtxt(path+"/rmsd.xvg",unpack=True)
    else:
        print "ERROR!"
        print "  No option for coordinate: ", coord
        print "  Exiting"
        raise SystemExit

    states = []
    for i in range(len(bounds)):
        print "  State: ", bounds[i][0], " is defined as between: ",bounds[i][2], bounds[i][3]
        states.append((bounds[i][2] <= data)*(data <= bounds[i][3]))

    return states

def get_Tf_choice(sub):
    if not os.path.exists(sub+"/Tf_choice.txt"):
        print "ERROR!"
        print "  Please create ",sub+"/Tf_choice.txt with your choice to do mutations at."
        print "  Exiting"
        raise SystemExit
    else:
        Tf_choice = open(sub+"/Tf_choice.txt").read().split()[0]
        print "  Calculating dH for temp ",Tf_choice
    return Tf_choice

def get_mutant_fij(mutants,keep_interactions):
    Fij = []
    i = 0
    for mut in mutants:
        fij_temp = np.loadtxt("mutants/fij_"+mut+".dat")
        fij_all = []
        for i in range(len(fij_temp)-4):
            fij_all.extend(fij_temp[i,i+4:])
        fij = np.array(fij_all)[keep_interactions != 0]
        if i == 0:
            Fij = np.zeros((len(mutants),len(fij)),float)
            Fij[0,:] = fij
        else:
            Fij[i,:] = fij
        i += 1
        
    return Fij
        
def load_eps_delta_sig_traj(subdir):
    ''' Load in the info from the BeadBead.dat file. Sig_ij, eps_ij, delta_ij and
        index pairs. This information is constant for a trajectory. Filter all fields
        to keep only interactions with nonzero interaction type.

        May be generalized in the future or moved inside Model to deal with Models with
        multiple parameters per interaction (e.g. desolvation barrier, etc.)
    '''
    print "  Loading BeadBead.dat"
    beadbead = np.loadtxt(subdir+"/BeadBead.dat",dtype=str) 
    sigij = beadbead[:,5].astype(float)
    epsij = beadbead[:,6].astype(float)
    deltaij = beadbead[:,7].astype(float)
    interaction_numbers = beadbead[:,4].astype(str)
    pairs = beadbead[:,:2].astype(int) 
    pairs -= np.ones(pairs.shape,int)

    keep_interactions = np.zeros(len(interaction_numbers),int)
    for i in range(len(interaction_numbers)):
        if interaction_numbers[i] in ["ds","ss"]:
            pass
        else:
            keep_interactions[i] = int(interaction_numbers[i])

    #print keep_interactions != 0       ## DEBUGGING
    #print sum((keep_interactions != 0).astype(int))      ## DEBUGGING
    sigij = sigij[keep_interactions != 0]
    epsij = epsij[keep_interactions != 0]
    deltaij = deltaij[keep_interactions != 0]
    pairs = pairs[keep_interactions != 0]

    print "  Only modifying ",sum((keep_interactions != 0).astype(int)), " parameters out of ", len(keep_interactions)
    ## Use mdtraj to compute the distances between pairs.
    print "  Loading traj.xtc with mdtraj..."
    traj = md.load(subdir+"/traj.xtc",top=subdir+"/Native.pdb")
    print "  Computing distances with mdtraj..."
    traj_dist = md.compute_distances(traj,pairs)

    return sigij,epsij,deltaij,interaction_numbers,keep_interactions,pairs,traj,traj_dist

def calculate_Qij(Model,r,sig,delta,interaction_nums):
    ''' Calculates the normalized interaction betwen nonbonded pairs.'''
    #if Model.interaction_types[0] == "LJ12-10":
    #    def Qij(r,sig,delta):
    #        return 5.*((sig/r)**12) - 6.*delta*((sig/r)**10)
    #else:
    #    print "ERROR!"
    #    print "  Unrecognized interaction type ", Model.interaction_types[0]
    #    print "  Exiting."
    #    raise SystemExit
    #print "  Number frames:", traj.n_frames,"  Number atoms:",traj.n_atoms

    print "  Calculating Qij..."
    qij = Model.nonbond_interaction(traj_dist,sigij,deltaij)
    return qij

def calculate_dH_for_mutants(Model,System,append_log):
    ''' First task is to calculate the perturbations for each mutation for
        each frame in the trajectory.

        In calculating the mutations only modify parameters that have interaction_type
        in the BeadBead.dat =/= [0,ds,ss]. 
    '''
    
    append_log(System.subdir,"Starting: Calculating_dH")

    cwd = os.getcwd()
    sub = cwd+"/"+System.subdir+"/"+System.mutation_active_directory
    T = get_Tf_choice(sub)
    savedir = sub+"/"+T+"_agg"

    os.chdir(System.subdir)

    mutants = [ x.split()[1]+x.split()[0]+x.split()[2] for x in open("mutants/mutations.txt","r").readlines()[1:] ]

    sigij,epsij,deltaij,interaction_nums,keep_interactions,pairs,traj,traj_dist = load_eps_delta_sig_traj(savedir)
    Fij = get_mutant_fij(mutants,keep_interactions)
    qij = calculate_Qij(Model,traj_dist,sigij,deltaij,interaction_nums)

    for j in range(len(fij)):
        mut = mutants[j]
        if not os.path.exists(savedir+"/dH_"+mut+".dat"):
            fij = Fij[j]
            print "    Computing dH vectorized for ", mut
            dH_k = -1.*np.array([ sum(x) for x in fij*qij ])
            print "    Saving dH for ",mut
            np.savetxt(savedir+"/dH_"+mut+".dat",dH_k)
    os.chdir(cwd)
     
    append_log(System.subdir,"Finished: Calculating_dH")

def get_mutant_dH(path,mutants):

    i = 0
    for mut in mutants:
        temp = np.loadtxt(path+"/dH_"+mut+".dat")
        print "    Loading:",mut
        if i == 0:
            dH = np.zeros((len(mutants),len(temp)),float)
            dH[i,:] = temp
        else:
            dH[i,:] = temp
        i += 1
    
    return dH

def calculate_phi_values(Model,System,append_log,coord="Q"):
    ''' Calculate the phi values for a trajectory.

        In calculating the mutations only modify parameters that have interaction_type
        in the BeadBead.dat =/= [0,ds,ss]. 
    '''
    
    append_log(System.subdir,"Starting: Calculating_phi_values")
    cwd = os.getcwd()
    sub = cwd+"/"+System.subdir+"/"+System.mutation_active_directory
    T = get_Tf_choice(sub)
    savedir = sub+"/"+T+"_agg"
    os.chdir(System.subdir)
    print "  Entering subdirecotory"

    mutants = [ x.split()[1]+x.split()[0]+x.split()[2] for x in open("mutants/mutations.txt","r").readlines()[1:] ]

    #sigij,epsij,deltaij,interaction_nums,keep_interactions,pairs,traj,traj_dist = load_eps_delta_sig_traj(savedir)
    #Fij = get_mutant_fij(mutants,keep_interactions)
    #qij = calculate_Qij(Model,traj_dist,sigij,deltaij,interaction_nums)

    if not os.path.exists(savedir+"/phi"):
        os.mkdir(savedir+"/phi")

    print "  Getting state bounds for coordinate:",coord
    states = get_state_bounds(savedir,coord)
    #print states
    print "  Loading dH for mutants"
    dH = get_mutant_dH(savedir,mutants[:10])

    print "  Computing phi values..."
    beta = 1./(GAS_CONSTANT_KJ_MOL*float(T))
    bracket_exp_D = sum(np.exp(-beta*dH[:,states[0]]).T)/float(dH[:,states[0]].shape)
    bracket_exp_TS = sum(np.exp(-beta*dH[:,states[1]]).T)/float(dH[:,states[1]].shape)
    bracket_exp_N = sum(np.exp(-beta*dH[:,states[2]]).T)/float(dH[:,states[2]].shape)

    ddG_dagger = (1./beta)*np.log(bracket_exp_D/bracket_exp_TS)
    ddG_circ = (1./beta)*np.log(bracket_exp_D/bracket_exp_N)
    print "Mutant ddG_dagger  ddG_circ  Phi"
    for i in range(len(ddG_dagger)):
        print "%6s%11.7f%10.7f%10.7f" % (mutants[i],ddG_dagger[i],ddG_circ[i],ddG_dagger[i]/ddG_circ[i])
    
    #for j in range(len(fij)):
    #    mut = mutants[j]
    #    if not os.path.exists(savedir+"/dH_"+mut+".dat"):
    #        fij = Fij[j]
    #        print "    Computing dH vectorized for ", mut
    #        dH_k = -1.*np.array([ sum(x) for x in fij*qij ])
    #        print "    Saving dH for ",mut
    os.chdir(cwd)
     
    append_log(System.subdir,"Finished: Calculating_phi_values")
    return dH,states

if __name__ == '__main__':
    def dummy_func(sub,string):
        pass 
    
    subdirs = ["r15"]
    Models = models.load_models(subdirs,dryrun=True)
    Systems = systems.load_systems(subdirs)
    Model = Models[0]
    System = Systems[0]

    path = System.subdir+"/"+System.mutation_active_directory+"/131.17_agg"
    #states = get_state_bounds(path,"Q") ## DEBUGGING
    dH, states = calculate_phi_values(Model,System,dummy_func)
