""" Start simulations in the folding temperature loop. Tf_loop

Description:

    This module will be the library for submitting the simulation jobs for the
Tf_loop (folding temperature loop). The Tf_loop tries to find the folding
temperature by determining the melting curve over a large spread in
temperatures then narrowing in on the transition point. The goal is to obtain
equilibrium simulations at the folding temperature.

"""

import numpy as np
import subprocess as sb
from glob import glob
import os
import argparse
import shutil

import mdp

def main():
    """ Use gmxcheck on subdirectories.  """
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--check', action='store_true', help='use gmxcheck on all subdirectories')
    args = parser.parse_args()
    if args.check == True:
        gmxcheck_subdirectories()
    else:
        pass

def check_completion(model,append_log,equil=False):
    """ Checks to see if the previous Tf_loop simulation completed. 

    Description:

        First 
    checks the desired number of steps in the .mdp file then 
    checks to see if md.log has recorded that number of steps.
    """

    name = model.subdir
    cwd = os.getcwd()
    if equil == True:
        sub = "%s/Mut_%d" % (name,model.Mut_iteration)
    else:
        sub = "%s/Tf_%d" % (name,model.Tf_iteration)
    os.chdir("%s/%s" % (cwd,sub))
    tempfile = open("T_array_last.txt","r").readlines()
    temperatures = [ temp[:-1] for temp in tempfile  ]
    error = 0
    for k in range(len(temperatures)):
        tdir = temperatures[k]
        check_error = run_gmxcheck(tdir)
        if check_error == 1:
            error = 1
        ## Determine the number of steps for completed run.
        for line in open("%s/nvt.mdp" % tdir,"r"):
            if line[:6] == "nsteps":
                nsteps = int(line.split()[2]) + 1
                break    
        finish_line = "Statistics over %d" % nsteps
        ## Check if md.log has finished the required number of steps.
        if finish_line in open("%s/md.log" % tdir,"r").read():
            append_log(name,"  %s finished." % tdir, subdir=True)
        else:
            print "    Check %s simulation did not finish." % tdir
            #print "    Cannot continue with errors."
            ## Try to restart the run if possible.
            if os.path.exists(tdir+"/rst.pbs"):
                os.chdir(tdir)
                qrst = "qsub rst.pbs"
                sb.call(qrst.split(),stdout=open("rst.out","w"),stderr=open("rst.err","w"))
                os.chdir(cwd+"/"+sub)
                append_log(name,"  %s did not finish. restarting" % tdir, subdir=True)
                print "  %s did not finish. Restarting: submitting rst.pbs. " % tdir
            else:
                append_log(name,"  %s did not finish. did not find a rst.pbs. skipping." % tdir, subdir=True)
            error = 1

    if error == 1:
        print "  Cannot continue until simulations complete. Check if all unfinished runs were restarted properly."
        pass 
    else:
        if equil == True:
            append_log(name,"Finished: Equil_Tf")
        else:
            append_log(name,"Finished: Tf_loop_iteration")
    model.error = error
    os.chdir(cwd)

def gmxcheck_subdirectories():
    """ Run gmxcheck on all traj.xtc files in subdirecories. """
    runs = glob("*/traj.xtc")
    dirs = [ x[:-9] for x in runs ]
    error = 0
    for subdir in dirs:
        cwd = os.getcwd()
        temp = run_gmxcheck(subdir)
        os.chdir(cwd)
        error += temp
    if error != 0:
        print "ERROR! Some trajectories did not pass gmxcheck."
        print " Exiting."
        raise SystemExit

def run_gmxcheck(subdir):
    print "  Running gmxcheck on ",subdir
    os.chdir(subdir)
    check = "gmxcheck -f traj.xtc"
    sb.call(check.split(),stdout=open("check.out","w"),stderr=open("check.err","w")) 
    
    errorcode = "Fatal error"
    if (errorcode in open("check.err","r").read()) or (errorcode in open("check.out","r").read()):
        print "  FATAL ERROR in directory: ",subdir
        print "  somethings wrong with Gromacs traj.xtc file. See %s/check.err" % subdir
        #print open("check.err","r").read()
        error = 1
    else:
        error = 0
    os.chdir("..")
    return error

def determine_new_T_array():
    """ Find the temperatures which bracket the folding temperature.
        This takes the temperatures at which the average fraction of
        nonhelical contacts falls below 0.5 as bracketing the folding 
        temperature. A more complicated calculation is probably 
        needed for more complicated systems (proteins with intermediates)"""
    temps = open("T_array_last.txt","r").readlines()
    temperatures = [ temp[:-1] for temp in temps ]
    temperatures.sort()
    lowerT = int(temperatures[0].split("_")[0])
    dT = int(temperatures[1].split("_")[0]) - lowerT
    upperT = int(temperatures[-1].split("_")[0])
    ## Temperatures bracket the folding temperature if the average 
    ## fraction of nonlocal native contacts goes from greater than 0.5 to less
    ## than 0.5.
    for tdir in temperatures:
        Q = np.loadtxt(tdir+"/Qnhprob.dat")
        avgQ = np.mean(Q[len(Q)/2:])
        if avgQ > 0.5*max(Q):
            lowerT = int(tdir.split("_")[0])
        else:
            upperT = int(tdir.split("_")[0])
            break
        
    if dT == 2:
        ## Previous run was final iteration. Now WHAM needs to be
        ## done.
        newT_min, newT_max, newdeltaT = 0,0,0
    else:
        ## Determine the finer grain T_array.
        newdeltaT = int(float(dT)/5.)
        ## If newdeltaT < 5 then just do finest temperature spacing. 
        if newdeltaT < 5:
            newdeltaT = 2
            midT = int(0.5*(float(lowerT)+upperT))
            newT_min = midT - 20
            newT_max = midT + 20
        else:
            newT_min = lowerT + newdeltaT
            newT_max = upperT - newdeltaT
    #print "##DEBUGGING: New Ti, Tf, dT", newT_min, newT_max, newdeltaT
    return newT_min, newT_max, newdeltaT

def manually_extend_temperatures(model,append_log,method,temps,factor):
    """ To manually extend some temperatures."""

    name = model.subdir
    cwd = os.getcwd()
    ## Determine directory to enter
    if method == "Tf":
        sub = "%s/%s/Tf_%d" % (model.path,name,model.Tf_iteration)
        Tlist = [ str(int(x))+"_0" for x in temps ]
    elif method == "Mut":
        sub = "%s/%s/Mut_%d" % (model.path,name,model.Mut_iteration)
        Tlist = []
        for i in range(len(temps)):
            for j in range(1,10):
                tempdir = "%.2f_%d" % (temps[i], j)
                if os.path.exists(sub+"/"+tempdir):
                    Tlist.append(tempdir) 
                else:
                    break

    os.chdir(sub)
    check_exist = [ os.path.exists(x) for x in Tlist ]
    ## Check that all temperaures exist 
    if not all(check_exist):
        print "ERROR!"
        print "  Some temperature does not exist!"
        for i in range(len(Tlist)):
            print "  Temp:", Tlist[i], check_exist[i]  
        print "  Exiting."
        os.chdir(cwd)
        raise SystemExit

    cwd2 = os.getcwd()
    for k in range(len(Tlist)):
        Tdir = Tlist[k]
        os.chdir(Tdir)
        T = Tdir.split("_")[0]
        if model.dry_run == True:
            print "    Dryrun Success! " 
            os.chdir(cwd)
            raise SystemExit
        else:
            extend_temperature(T,factor)
            if os.path.exists("Q.dat"):
                os.remove("Q.dat")
            if os.path.exists("energyterms.xvg"):
                os.remove("energyterms.xvg")
        os.chdir(cwd2)
    if method == "Tf":
        append_log(name,"Starting: Tf_loop_iteration")
    elif method == "Mut":
        append_log(name,"Starting: Equil_Tf")

    os.chdir(cwd)

def extend_temperature(T,factor):
    """ Extend individual temperature run by factor """
    ## Calculate new nsteps = factor*old_nsteps
    for line in open("nvt.mdp","r").readlines():
        if line.startswith("nsteps"):
            old_nsteps = int(line.split()[2])
            new_nsteps = str(int(round(factor*old_nsteps)))
            break
    
    ## Save old .mdp and .tpr as something else.
    shutil.move("nvt.mdp","nvt.mdp")
    shutil.move("topol_4.6.tpr","old_topol_4.6.tpr")

    ## Write new .mdp with more steps and recreate .tpr
    mdpfile = mdp.get_constant_temperature_mdp_smog(T,new_nsteps)
    open("nvt.mdp","w").write(mdpfile)

    print "  Extending temp ", T, " to nsteps ",new_nsteps
    prep_step1 = 'grompp_sbm -n index.ndx -f nvt.mdp -c conf.gro -p topol.top -o topol_4.5.tpr '
    prep_step2 = 'grompp -n index.ndx -f nvt.mdp -c conf.gro -p topol.top -o topol_4.6.tpr '
    sb.call(prep_step1.split(),stdout=open("sim.out","w"),stderr=open("sim.err","w"))
    sb.call(prep_step2.split(),stdout=open("sim.out","w"),stderr=open("sim.err","w"))

    ## Submit rst.pbs
    qsub = "qsub rst.pbs"
    sb.call(qsub.split(),stdout=open("rst.out","w"),stderr=open("rst.err","w"))

def folding_temperature_loop(model,append_log,new=False):
    """ The "folding temperature loop" is one of the several large-scale 
        logical structures in modelbuilder. It is entered anytime we want
        to determine the folding temperature. This could be when we have
        started a new project, refined the paramters, or returned to a 
        project in progress. The folding temperature loop successively 
        narrows in on the folding temperature."""

    cwd = os.getcwd()
    sub = model.path+"/"+model.subdir+"/Tf_"+str(model.Tf_iteration)
    #print sub  ## DEBUGGING
    if (not os.path.exists(sub)):
        os.mkdir(sub)
    ## Check to see if the folding temperature has been found. If yes, then continue.
    if (not os.path.exists(sub+"/Tf.txt")):
        os.chdir(sub)
        folding_temperature_loop_extension(model,append_log,new=new)
    else:
        ## Folding temperature has been found. Continuing.
        pass
    os.chdir(cwd)

def folding_temperature_loop_extension(model,append_log,new=False):
    """ This is for doing an additional loop in the Tf_loop. It either starts
        an initial temperature array or refines the temperature range according
        to previous data. """
    ## Check to see if a previous temperature range was used.
    if (not os.path.exists("T_array_last.txt")) or new:
        ## For initial exploration use very broad temperature increments.
        if model.initial_T_array != None:
            T_min = model.initial_T_array[0]
            T_max = model.initial_T_array[1]
            deltaT = model.initial_T_array[2]
        else:
            ## Estimate folding temperature
            if (model.contact_type == "LJ1210") and (model.n_repcontacts != 0):
                E = float(sum(model.contact_epsilons[model.LJtype == 1])) - float(sum(model.contact_epsilons[model.LJtype == -1]))
            else:
                E = float(sum(model.contact_epsilons))
            N = float(model.n_residues)
            Tf_guess = int(round((36.081061*E/N) + 56.218196)) ## calibration for LJ1210 contacts circa June 2014
            if model.contact_type == "Guassian":
                T_min = Tf_guess - 60
                T_max = Tf_guess + 10
            else:
                T_min = Tf_guess - 20
                T_max = Tf_guess + 20
            deltaT = 4
    else:
        ## Use previous range to determine new range. 
        T_min, T_max, deltaT = determine_new_T_array()
    print "  Running temperature array: T_initial = %.2f   T_final = %.2f   dT = %.2f " % (T_min,T_max,deltaT)
    run_temperature_array(model,T_min,T_max,deltaT)
    append_log(model.subdir,"Submitting T_array iteration %d " % model.Tf_iteration)
    append_log(model.subdir,"  T_min = %d , T_max = %d , dT = %d" % (T_min, T_max, deltaT))
    append_log(model.subdir,"Starting: Tf_loop_iteration")

def start_next_Tf_loop_iteration(model,append_log):
    """ Estimate new folding temperature with calibration data

    Description:

        We made a calibration curve with the following points.
    """

    ## Update System counters and estimate new Tf
    model.Tf_iteration += 1
    model.Mut_iteration += 1
    ## Estimate folding temperature
    if (model.contact_type == "LJ1210") and (model.n_repcontacts != 0):
        E = float(sum(model.contact_epsilons[model.LJtype == 1])) - float(sum(model.contact_epsilons[model.LJtype == -1]))
    else:
        E = float(sum(model.contact_epsilons))
    N = float(model.n_residues)
    Tf_guess = (36.081061*E/N) + 56.218196 ## calibration for LJ1210 contacts circa June 2014
    if model.contact_type == "Gaussian":
        T_min = Tf_guess - 60
        T_max = Tf_guess + 10
    else:
        T_min = Tf_guess - 20
        T_max = Tf_guess + 20
    T_min = int(round(T_min))
    T_max = int(round(T_max))
    deltaT = 4

    cwd = os.getcwd()
    sub = "%s/%s/Tf_%d" % (model.path,model.subdir,model.Tf_iteration)
    if os.path.exists(sub):
        print "ERROR!"
        print "  The next Tf iteration directory exists. "
        print "  exiting"
        raise SystemExit
    else:
        os.makedirs(sub)
    os.chdir(sub)

    run_temperature_array(model,T_min,T_max,deltaT)
    append_log(model.subdir,"Submitting T_array iteration %d" % model.Tf_iteration)
    append_log(model.subdir,"  T_min = %d , T_max = %d , dT = %d" % (T_min, T_max, deltaT))
    append_log(model.subdir,"Starting: Tf_loop_iteration")
    os.chdir(cwd)

def manually_add_temperature_array(model,append_log,T_min,T_max,deltaT):
    """ To manually set the next temperature array."""
    cwd = os.getcwd()
    sub = model.path+"/"+model.subdir+"/Tf_"+str(model.Tf_iteration)
    os.chdir(sub)
    append_log(model.subdir,"Submitting T_array iteration %d " % model.Tf_iteration)
    append_log(model.subdir,"  T_min = %d , T_max = %d , dT = %d" % (T_min, T_max, deltaT))
    run_temperature_array(model,T_min,T_max,deltaT)
    append_log(model.subdir,"Starting: Tf_loop_iteration")
    os.chdir(cwd)

def manually_add_equilibrium_runs(model,append_log,temps):
    """ To manually set the next temperature array."""
    name = model.subdir
    cwd = os.getcwd()
    sub = "%s/%s/Mut_%d" % (model.path,name,model.Mut_iteration)
    os.chdir(sub)
    ## Run for longer if the protein is really big.
    walltime, queue, ppn, nsteps = determine_equil_walltime(model)

    T_string = ''
    for i in range(len(temps)):
        T = "%.2f" % temps[i]
        for simnum in range(1,4):
            simpath = T+"_"+str(simnum)
            ## Only start the simulation if directory doesn't exist.
            if (not os.path.exists(simpath)):
                T_string += "%s\n" % simpath
                os.mkdir(simpath)
                os.chdir(simpath)
                append_log(name,"  running T=%s" % simpath, subdir=True)
                print "    Running temperature ", simpath
                run_constant_temp(model,T,nsteps=nsteps,walltime=walltime,queue=queue)
                os.chdir("..")
            else:
                ## Directory exists for this temperature: continue.
                continue

    open("T_array.txt","a").write(T_string)
    open("T_array_last.txt","w").write(T_string)
    append_log(name,"Starting: Equil_Tf")
    os.chdir(cwd)

def run_equilibrium_simulations(model,append_log):
    """ Run very long (equilibrium) simulations at the estimated folding 
        temperature."""

    name = model.subdir
    cwd = os.getcwd()
    mutsub = model.path+"/"+model.subdir+"/Mut_"+str(model.Mut_iteration)
    Tfsub = model.path+"/"+model.subdir+"/Tf_"+str(model.Tf_iteration)
    Tf = open(Tfsub+"/Tf.txt","r").read().split()[0]

    append_log(name,"Starting Equil_Tf", subdir=True)
    walltime, queue, ppn, nsteps = determine_equil_walltime(model)



    if not os.path.exists(mutsub):
        os.mkdir(mutsub)
    os.chdir(mutsub)
    T_string = ''
    for n in range(3):
        T = "%.2f" % (float(Tf)+1.*(n-1))
        for simnum in range(1,4):
            simpath = T+"_"+str(simnum)
            ## Only start the simulation if directory doesn't exist.
            if (not os.path.exists(simpath)):
                T_string += "%s\n" % simpath
                os.mkdir(simpath)
                os.chdir(simpath)
                append_log(name,"  running T=%s" % simpath, subdir=True)
                print "    Running temperature ", simpath
                run_constant_temp(model,T,nsteps=nsteps,walltime=walltime,queue=queue)
                os.chdir("..")
            else:
                ## Directory exists for this temperature: continue.
                continue

    open("T_array.txt","a").write(T_string)
    open("T_array_last.txt","w").write(T_string)
    append_log(model.subdir,"Starting: Equil_Tf")
    os.chdir(cwd)

def determine_equil_walltime(model):
    """ Estimate an efficient walltime."""
    N = model.n_residues
    ppn = "1"
    nsteps = "500000000"
    queue="serial"
    if N < 60:
        walltime="16:00:00"
    else:
        if N > 100:
            queue="serial_long"
            walltime="20:00:00"
        else:
            walltime="15:00:00"
    return walltime, queue, ppn,nsteps

def determine_walltime(model):
    """ Estimate an efficient walltime."""
    N = model.n_residues
    ppn = "1"
    nsteps = "100000000"
    queue="serial"
    if N < 60:
        walltime="03:00:00"
    else:
        if N > 100:
            if N > 200:
                walltime="15:00:00"
            else:
                walltime="5:00:00"
        else:
            walltime="3:00:00"
    return walltime, queue, ppn,nsteps

def run_temperature_array(model,T_min,T_max,deltaT):
    """ Simulate range of temperatures to find the folding temperature. """

    Temperatures = range(T_min,T_max+deltaT,deltaT)
    ## Run for longer if the protein is really big.
    walltime, queue, ppn, nsteps = determine_walltime(model)

    T_string = ''
    for T in Temperatures:
        simpath = str(T)+"_0"
        ## Only start the simulation is directory doesn't exist.
        if (not os.path.exists(simpath)):
            T_string += "%d_0\n" % T
            os.mkdir(simpath)
            os.chdir(simpath)
            if not model.dry_run:
                print "  Running temperature ", T
            run_constant_temp(model,T,nsteps=nsteps,walltime=walltime,queue=queue,ppn=ppn)
            os.chdir("..")
        else:
            continue
    open("T_array.txt","a").write(T_string)
    open("T_array_last.txt","w").write(T_string)
    open("Ti_Tf_dT.txt","w").write("%d %d %d" % (T_min, T_max, deltaT))

def run_constant_temp(model,T,nsteps="100000000",walltime="23:00:00",queue="serial",ppn="1"):
    ''' Start a constant temperature simulation with Gromacs. 

    Description:

        Save the grofile and topology file in model object, then 
    submit a pbs job to run simulation.

    '''
    ## Loading and writing grompp.
    mdpfile = mdp.get_constant_temperature_mdp_smog(str(T),nsteps)
    open("nvt.mdp","w").write(mdpfile)

    ## Write all needed simulation files.
    open("Native.pdb","w").write(model.cleanpdb)
    open("index.ndx","w").write(model.index_ndx)
    open("dihedrals.ndx","w").write(model.dihedrals_ndx)
    open("contacts.ndx","w").write(model.contacts_ndx)
    open("conf.gro","w").write(model.grofile)
    open("topol.top","w").write(model.topology)
    open("BeadBead.dat","w").write(model.beadbead)

    repstring = None
    if model.contact_type == "LJ1210":
        np.savetxt("table.xvg",model.table,fmt="%16.15e",delimiter=" ")
        if model.n_repcontacts != 0:
            repstring = ""
            for i in range(model.n_repcontacts):
                repstring += "%s " % model.rep_tablenames[i]
                np.savetxt(model.rep_tablenames[i],model.rep_tables[i],fmt="%16.15e",delimiter=" ")
        

    np.savetxt("Qref_cryst.dat",model.Qref,fmt="%1d",delimiter=" ")
    np.savetxt("contacts.dat",model.contacts,fmt="%4d",delimiter=" ")

    ## Start simulation
    jobname = model.subdir+"_"+str(T)
    if model.contact_type == "Gaussian":
        prep_run(jobname,walltime=walltime,queue=queue,ppn=ppn,contact_type="Gaussian",repstring=repstring)
    else:
        prep_run(jobname,walltime=walltime,queue=queue,ppn=ppn,repstring=repstring)

    if model.dry_run == True:
        print "    Dryrun: Successfully saved simulation files for ", T
    else:
        qsub = "qsub run.pbs"
        sb.call(qsub.split(),stdout=open("sim.out","w"),stderr=open("sim.err","w"))
    
def get_pbs_string(jobname,queue,ppn,walltime,contact_type=None,repstring=None):
    """ Return basic PBS job script. """
    pbs_string = "#!/bin/bash \n"
    pbs_string +="#PBS -N %s \n" % jobname
    pbs_string +="#PBS -q %s \n" % queue
    pbs_string +="#PBS -l nodes=1:ppn=%s \n" % ppn
    pbs_string +="#PBS -l walltime=%s \n" % walltime
    pbs_string +="#PBS -V \n\n"
    pbs_string +="cd $PBS_O_WORKDIR\n"
    if contact_type == "Gaussian":
        #pbs_string +="mdrun_sbm -nt 1 -s topol_4.5.tpr -table table.xvg -tablep table.xvg"
        pbs_string +="mdrun_sbm -s topol_4.5.tpr -table table.xvg -tablep table.xvg"
    else:
        #pbs_string +="mdrun -nt 1 -s topol_4.6.tpr -table table.xvg -tablep table.xvg"
        pbs_string +="mdrun -s topol_4.6.tpr -table table.xvg -tablep table.xvg"
    #pbs_string +="mdrun -s topol_4.6.tpr -table table.xvg -tablep table.xvg"
    return pbs_string

def get_rst_pbs_string(jobname,queue,ppn,walltime,contact_type=None,repstring=None):
    """ Return basic PBS job script for restarting. """
    pbs_string = "#!/bin/bash \n"
    rst_string = "#!/bin/bash \n"
    rst_string +="#PBS -N %s_rst \n" % jobname
    rst_string +="#PBS -q %s \n" % queue
    rst_string +="#PBS -l nodes=1:ppn=%s \n" % ppn
    rst_string +="#PBS -l walltime=%s \n" % walltime
    rst_string +="#PBS -V \n\n"
    rst_string +="cd $PBS_O_WORKDIR\n"
    if contact_type == "Gaussian":
        #rst_string +="mdrun_sbm -nt 1 -s topol_4.5.tpr -table table.xvg -tablep table.xvg -cpi state.cpt"
        rst_string +="mdrun_sbm -s topol_4.5.tpr -table table.xvg -tablep table.xvg -cpi state.cpt"
    else:
        #rst_string +="mdrun -nt 1 -s topol_4.6.tpr -table table.xvg -tablep table.xvg -cpi state.cpt"
        if repstring != None:
            rst_string +="mdrun -s topol_4.6.tpr -table table.xvg -tablep table.xvg -cpi state.cpt "
        else:
            rst_string +="mdrun -s topol_4.6.tpr -table table.xvg -tablep table.xvg -cpi state.cpt"
    #rst_string +="mdrun -s topol_4.6.tpr -table table.xvg -tablep table.xvg -cpi state.cpt"
    return rst_string

def prep_run(jobname,walltime="23:00:00",queue="serial",ppn="1",contact_type=None,repstring=None):
    ''' Executes the constant temperature runs.'''

    prep_step1 = 'grompp_sbm -n index.ndx -f nvt.mdp -c conf.gro -p topol.top -o topol_4.5.tpr'
    prep_step2 = 'grompp -n index.ndx -f nvt.mdp -c conf.gro -p topol.top -o topol_4.6.tpr'
    sb.call(prep_step1.split(),stdout=open("prep.out","w"),stderr=open("prep.err","w"))
    sb.call(prep_step2.split(),stdout=open("prep.out","w"),stderr=open("prep.err","w"))

    pbs_string = get_pbs_string(jobname,queue,ppn,walltime,contact_type=contact_type,repstring=repstring)
    open("run.pbs","w").write(pbs_string)

    rst_string = get_rst_pbs_string(jobname,queue,ppn,walltime,contact_type=contact_type,repstring=repstring)
    open("rst.pbs","w").write(rst_string)

if __name__ == '__main__':
    main()
