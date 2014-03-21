import os
from system import System


class NewSystem(System):
    def __init__(self,subdir,Tf_it=0,Tf_act_dir='Tf_0',Tf_refine=[0],
                 Mut_it=0,Mut_act_dir='Mut_0'):
        self.path = os.getcwd()
        self.subdir = subdir 
        self.pdb = subdir + ".pdb" 
        self.error = 0 

        self.initial_T_array = None
        self.Tf_iteration = Tf_it
        self.Tf_active_directory = Tf_act_dir
        self.Tf_refinements = Tf_refine
        self.mutation_iteration = Mut_it 
        self.mutation_active_directory = Mut_act_dir

        ## These parameters should be held exclusively by Model.
        self.nonbond_params = []
        self.R_CD = []
        self.Qrefs = []
        self.itp_files = []
        
    def __repr__(self):
        reprstring = "[ Path ]\n"
        reprstring += "%s\n" % self.path
        reprstring += "[ PDB ]\n"
        reprstring += "%s\n" % self.pdb
        reprstring += "[ Subdir ]\n"
        reprstring += "%s\n" % self.subdir
        reprstring += "[ Tf_Iteration ]\n"
        reprstring += "%s\n" % self.Tf_iteration
        reprstring += "[ Tf_Refinements ]\n"
        temp = ""
        for x in self.Tf_refinements:
            temp += "%d\n" % int(x)
        reprstring += "%s" % temp
        reprstring += "[ Tf_Active_Directory ]\n"
        reprstring += "%s\n" % self.Tf_active_directory
        reprstring += "[ Mut_Iteration ]\n"
        reprstring += "%s\n" % self.mutation_iteration
        reprstring += "[ Mut_Active_Directory ]\n"
        reprstring += "%s\n" % self.mutation_active_directory

        reprstring += "[ R_CD ]\n"
        reprstring += "\n"
        
        return reprstring
