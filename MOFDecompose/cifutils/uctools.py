
from __future__ import division
import os
import sys
import string
import copy
import CifFile
from types import *
from math import sin,cos,pi,sqrt,pow,ceil,floor
from utils import *
from spacegroupdata import *
from elementdata import *
from random import random, gauss
from fractions import gcd
# from math import gcd
from functools import reduce


class CellData(GeometryObject):

    def __init__(self):
        GeometryObject.__init__(self)
        self.initialized = False
        self.force = False    # Force generation despite problems?
        self.cartesianInput = False
        self.filename = ""
        self.blockname = ""
        self.quiet = True
        self.coordepsilon = 0.0002
        self.HallSymbol = ""
        self.spacegroupnr = 0
        self.HMSymbol = ""
        self.spacegroupsetting = ""
        self.cart_trans_matrix = None
        self.cart_trans_vector = None
        self.lattrans = LatticeMatrix([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        self.transvecs = [LatticeVector([zero, zero, zero])]
        self.symops = set([])
        self.ineqsites = []
        self.occupations = []
        self.atomdata = []
        self.atomset = set([])
        self.numberOfAtoms = None
        self.ChemicalComposition = dict([])
        # initial lattice parameters
        self.ainit = 0.
        self.binit = 0.
        self.cinit = 0.
        self.alphainit = 0.
        self.betainit = 0.
        self.gammainit = 0.
        self.coainit = 1.
        self.boainit = 1.
        # lattice parameters used to generate the cell
        self.a = 0.
        self.b = 0.
        self.c = 0.
        self.alpha = 0.
        self.beta = 0.
        self.gamma = 0.
        self.coa = 1.
        self.boa = 1.
        self.latticevectors = None
        self.lengthscale = 1.
        self.unit = "angstrom"
        self.alloy = False
        self.numofineqsites = 0
        # Lattice vector choices
        self.primcell = False
        self.rhomb2hex = False
        self.rhombohedral = False
        self.supercell = False

    def newunit(self,newunit="angstrom"):
        """ Set new unit for the length scale. Valid choices are:
            * angstrom
            * bohr  (bohr radii, or a.u. (atomic unit))
            * nm    (nanometer)
        """
        if self.unit == newunit:
            return
        if self.unit == "angstrom" and newunit == "bohr":
            fact = 1.8897261
        elif self.unit == "bohr" and newunit == "angstrom":
            fact = 0.52917721
        elif self.unit == "angstrom" and newunit == "nm":
            fact = 0.1
        elif self.unit == "nm" and newunit == "angstrom":
            fact = 10
        elif self.unit == "bohr" and newunit == "nm":
            fact = 0.052917721
        elif self.unit == "nm" and newunit == "bohr":
            fact = 18.897261
        else:
            raise CellError("newunit: "+newunit+" No such unit.")
        self.lengthscale *= fact
        self.a *= fact
        self.b *= fact
        self.c *= fact
        self.unit = newunit

    def crystal_system(self):
        return crystal_system(self.spacegroupnr)

    def conventional_latticevectors(self):
        # Set up Bravais lattice vectors of the conventional cell
        self.coa = self.c / self.a
        self.boa = self.b / self.a
        alphar = self.alpha*pi/180
        betar  = self.beta*pi/180
        gammar = self.gamma*pi/180
        if self.crystal_system() == 'cubic':
            latticevectors = LatticeMatrix([[one, zero, zero],
                                            [zero, one, zero],
                                            [zero, zero, one]])
        elif self.crystal_system() == 'hexagonal':
            latticevectors = LatticeMatrix([[sin(gammar), cos(gammar), zero],
                                            [zero, one, zero],
                                            [zero, zero, self.coa]])
        elif self.crystal_system() == 'tetragonal' or self.crystal_system() == 'orthorhombic':
            latticevectors = LatticeMatrix([[one, zero, zero],
                                            [zero, self.boa, zero],
                                            [zero, zero, self.coa]])
        ## elif self.crystal_system() == 'monoclinic':
        ##     latticevectors = LatticeMatrix([[one, zero, zero],
        ##                                     [zero, self.boa, zero],
        ##                                     [self.coa*cos(betar), zero, self.coa*sin(betar)]])
        elif self.crystal_system() == 'trigonal':
            # Hexagonal cell taken as conventional
            if not abs(self.gamma-120) < self.coordepsilon:
                gammar = 120*pi/180
            latticevectors = LatticeMatrix([[sin(gammar), cos(gammar), zero],
                                            [zero, one, zero],
                                            [zero, zero, self.coa]])
        elif self.crystal_system() == 'triclinic' or self.crystal_system() == 'monoclinic' or self.crystal_system() == 'unknown':
            angfac1 = (cos(alphar) - cos(betar)*cos(gammar))/sin(gammar)
            angfac2 = sqrt(sin(gammar)**2 - cos(betar)**2 - cos(alphar)**2
                       + 2*cos(alphar)*cos(betar)*cos(gammar))/sin(gammar)
            latticevectors = LatticeMatrix([[one, zero, zero],
                                            [self.boa*cos(gammar), self.boa*sin(gammar), zero],
                                            [self.coa*cos(betar), self.coa*angfac1, self.coa*angfac2]])
        else:
            raise SymmetryError("No support for "+self.crystal_system()+" crystal systems.")
        return latticevectors

    # The reciprocal lattice vectors corresponding to the lattice vectors of the structure
    # (b1, b2, b3)^T = 2 * pi * (a1, a2, a3)^{-1}
    def reciprocal_latticevectors(self):
        t = minv3(self.latticevectors)
        reclatvect = []
        for j in range(3):
            reclatvect.append([])
            for i in range(3):
                reclatvect[j].append(t[i][j]*2*pi)
        return LatticeMatrix(reclatvect)

    # Define comparison functions
    def poscomp(self, pos1, pos2):
        # Return True if two positions are the same
        if abs(pos1[0] - pos2[0]) < self.coordepsilon and \
               abs(pos1[1] - pos2[1]) < self.coordepsilon and \
               abs(pos1[2] - pos2[2]) < self.coordepsilon:
            return True
        else:
            return False

    def transveccomp(self, pos1,pos2):
        # Return True if two positions only differ by one
        # of the induced lattice translations
        match = False
        for tv in self.transvecs:
            if (abs(pos1[0]-(pos2[0]-tv[0]))<self.coordepsilon and \
                abs(pos1[1]-(pos2[1]-tv[1]))<self.coordepsilon and \
                abs(pos1[2]-(pos2[2]-tv[2]))<self.coordepsilon):
                match = True
        return match

    def duplicates(self, poslist, compfunc = transveccomp):
        # Return list of indices of duplicates in a list,
        # sorted in reverse order to be easy to use for removing the duplicates.
        # Optionally supply a comparison function for when two coordinates
        # are the same, else use 'samecoords' function from above.
        removeindices = set([])
        for i in range(len(poslist)):
            for j in range(len(poslist)-1,i,-1):
                if compfunc(self,poslist[i],poslist[j]):
                    removeindices.add(j)
        removeindices = list(removeindices)
        removeindices.sort(reverse=True)
        return removeindices

    def volume(self):
        """ Return the volume of the cell. """
        return abs(det3(self.latticevectors))

    def natoms(self):
        """ Return the number of atoms in the cell. """
        i = 0
        for a in self.atomdata:
            i += len(a)
        return i

    def primitive(self):
        """ Return a CrystalStructure object for the primitive cell."""
        self.getCrystalStructure(reducecell=True)
        return self

    def conventional(self):
        """ Return a CrystalStructure object for the conventional cell."""
        w = self.getCrystalStructure(reducecell=False)
        return w

    # Fill out sites that are not occupied to 100% with
    # empty spheres (optionally giving a label).
    def fill_out_empty(self,label="Em"):
        for a in self.atomdata:
            # Check concentration
            t = 0.0
            for sp,conc in a[0].species.items():
                t += conc
            # Add vacuum spheres if partially empty
            if abs(1.0-t) > a[0].compeps:
                for b in a:
                    b.species[label] = 1.0-t

    # Randomly displace atoms
    def randomDisplacements(self, size=0.1, distribution="uniform"):
        """
        Randomly displace all atoms. The size parameter gives the maximal
        deviation in whatever the real space unit currently is (typically Angstrom).
        The random displacements are uniformly distributed in the interval ]-size,size[.
        """
        invlatvecs = minv3(self.latticevectors)
        tmp = []
        i = 0
        for a in self.atomdata:
            for b in a:
                if distribution == "gaussian":
                    r = gauss(0.0,size)*size
                    theta = gauss(0.0, size)*pi
                    phi = gauss(0.0, size)*2*pi
                elif distribution == "uniform":
                    r = random()*size
                    theta = random()*pi
                    phi = random()*2*pi
                else:
                    raise SetupError("Unknown distribution for random displacements.")
                d = Vector([r*sin(theta)*cos(phi), r*sin(theta)*sin(phi), r*cos(theta)]).transform(invlatvecs)
                b.position = LatticeVector([b.position[i] + d[i] for i in range(3)])
                tmp.append([b])
        # We need to reset implicit symmetry information here
        self.atomdata = tmp

    def getCrystalStructure(self, reducecell=False):
        """
        Return a CrystalStructure object, either as it is or reduced to the
        primitive cell.
        """
        # reduce to primitive cell?
        self.primcell = reducecell

        ###################################
        #   INITIALIZE SPACE GROUP DATA   #
        ###################################
        # Try to set Hall symbol, if not set
        if self.HallSymbol == "":
            if self.HMSymbol == "":
                if 0 < self.spacegroupnr <= 230:
                    try:
                        self.HallSymbol = Number2Hall[self.spacegroupnr]
                    except:
                        raise SymmetryError("Found neither Hall nor H-M symbol and space group %i does not have a unique setting."%self.spacegroupnr)
                else:
                    if self.force:
                        sys.stderr.write("***Warning: CIF file contains neither space group symbols nor space group number.\n")
                        sys.stderr.write("            Defaulting to P 1. Check results carefully!\n")
                        self.HallSymbol = "P 1"
                    else:
                        raise SymmetryError("CIF file contains neither space group symbols nor space group number.")
            try:
                self.HallSymbol = HM2Hall[self.HMSymbol]
            except:
                sys.stderr.write("***Warning: Cannot convert "+self.HMSymbol+" to Hall symbol.\n")

        # Set space group number and H-M symbol if not set
        if not 0 < self.spacegroupnr <= 230:
            try:
                self.spacegroupnr = Hall2Number[self.HallSymbol]
            except:
                pass
        if self.HMSymbol == "":
            try:
                self.HMSymbol == Hall2HM[self.HallSymbol]
            except:
                pass

        # Check if we know enough:
        # To produce the conventional cell (self.primcell=False) we don't need the space group
        # symbol or number as long as we have the symmetry operations (equivalent sites).
        if self.spacegroupsetting == "":
            try:
                self.spacegroupsetting = self.HallSymbol.lstrip("-")[0]
            except:
                try:
                    self.spacegroupsetting = self.HMSymbol[0]
                except:
                    pass
        if self.spacegroupsetting == "":
            try:
                self.spacegroupsetting = SGnrtoHM[str(self.spacegroupnr)][0]
            except:
                pass
        # Sanity test of lattice parameters
        if self.a!=0 and self.b!=0 and self.c!=0 and self.alpha!=0 and self.beta!=0 and self.gamma!=0:
            if not 0 < self.spacegroupnr < 231:
                if len(self.symops) >= 1:
                    if self.primcell == True:
                        if self.spacegroupsetting == 'P':
                            self.spacegroupnr = 0
                        else:
                            raise SymmetryError("Insufficient symmetry information to reduce to primitive cell"+\
                                                " (need space group number or Hermann-Mauguin symbol).\n"+\
                                                "  Run with --no-reduce to generate cell in the conventional setting.")
                    else:
                        self.spacegroupnr = 0
        else:
            raise CellError("No crystallographic parameter may be zero.")

        # If no symmetry operations are not set, get internally stored.
        if not self.symops:
            eqsites = SymOpsHall[self.HallSymbol]
            # Define the set of space group operations.
            self.symops = set([])
            for site in eqsites:
                self.symops.add(SymmetryOperation(site))

        ############################
        #    INITIALIZE LATTICE    #
        ############################
        # Special case: trigonal systems in rhombohedral setting
        # are first transformed to hexagonal setting
        if self.HallSymbol in Rhomb2HexHall and abs(self.gamma - 120) > self.coordepsilon:
            self.rhomb2hex = True
            self.c = self.a * sqrt(3 + 6*cos(self.alpha*pi/180))
            self.a = 2 * self.a * sin(self.alpha*pi/360)
            self.b = self.a
            self.alpha = 90.0
            self.beta = 90.0
            self.gamma = 120.0
            rhomb2hextrans= LatticeMatrix([[2*third, third, third],
                                           [-third, third, third],
                                           [-third, -2*third, third]])
            for i in range(len(self.ineqsites)):
                self.ineqsites[i] = Vector(mvmult3(rhomb2hextrans,self.ineqsites[i]))
            # We also need the correct symmetry operations.
            eqsites = SymOpsHall[Rhomb2HexHall[self.HallSymbol]]
            self.symops = set([])
            for site in eqsites:
                self.symops.add(SymmetryOperation(site))
        # set primitive lattice vectors
        self.latticevectors = self.conventional_latticevectors()
        self.lengthscale = self.a
        self.alloy = False

        # Transform ineqsites to lattice coordinates if they were given as
        # cartesian in the input file.
        if self.cartesianInput:
            try:
                trans_matrix = minv3(self.cart_trans_matrix)
            except:
                if self.force:
                    # Fallback on the transformation matrix from default lattice vector choices.
                    t = []
                    for i in range(3):
                        t.append([])
                        for j in range(3):
                            t[i].append(self.latticevectors[i][j] * self.lengthscale)
                    trans_matrix = LatticeMatrix(minv3(t))
                else:
                    raise CellError("Failed to perform transformation from cartesian to lattice coordinates.")
            try:
                # Primarily use the transformation matrix/translation vector given as input.
                for i in range(len(self.ineqsites)):
                    t = self.ineqsites[i] - self.cart_trans_vector
                    self.ineqsites[i] = Vector(mvmult3(trans_matrix,t))
            except:
                raise CellError("Failed to perform transformation from cartesian to lattice coordinates.")

        ###############################
        #     LATTICE TRANSLATIONS    #
        ###############################
        #
        # Choices of lattice vectors made to largely coincide with the choices
        # made at http://cst-www.nrl.navy.mil/lattice/
        #
        # The induced translation vectors are from Zachariasen, "Theory of x-ray
        # diffraction in crystals".
        #
        # Relations between rhombohedral and hexagonal settings of trigonal
        # space groups from Tilley, "Crystals and crystal structures"
        # Bravais lattice vectors:
        #
        # a_r =  2/3 a_h + 1/3 b_h + 1/3 c_h
        # b_r = -1/3 a_h + 1/3 b_h + 1/3 c_h
        # c_r = -1/3 a_h - 2/3 b_h + 1/3 c_h
        #
        # a_h = a_r - b_r
        # b_h = b_r - c_r
        # c_h = a_r + b_r + c_r
        #
        # a, c and rhombohedral angle alpha:
        #
        # a_h = 2 * a_r * sin(alpha/2)
        # c_h = a_r * sqrt(3 + 6*cos(alpha))
        #
        # a_r = sqrt(3*a_h^2 + c_h^2) / 3
        # sin(alpha/2) = 3*a_h / (2 * sqrt(3*a_h^2 + c_h^2))
        #
        if self.primcell:
            if self.spacegroupsetting == 'I':
                # Body centered
                self.transvecs = [LatticeVector([zero,zero,zero]),
                                  LatticeVector([half,half,half])]
                if self.crystal_system() == 'cubic':
                    self.lattrans = LatticeMatrix([[-half, half, half],
                                                   [half, -half, half],
                                                   [half, half, -half]])
                else:
                    self.lattrans = LatticeMatrix([[one, zero, zero],
                                                   [zero, one, zero],
                                                   [half, half, half]])
            elif self.spacegroupsetting == 'F':
                # face centered
                self.transvecs = [LatticeVector([zero,zero,zero]),
                                  LatticeVector([half,half,zero]),
                                  LatticeVector([half,zero,half]),
                                  LatticeVector([zero,half,half])]
                self.lattrans = LatticeMatrix([[half, half, zero],
                                               [half, zero, half],
                                               [zero, half, half]])
            elif self.spacegroupsetting == 'A':
                # A-centered
                self.transvecs = [LatticeVector([zero,zero,zero]),
                                  LatticeVector([zero,half,half])]
                self.lattrans = LatticeMatrix([[one, zero, zero],
                                               [zero, half, -half],
                                               [zero, half, half]])
            elif self.spacegroupsetting == 'B':
                # B-centered
                self.transvecs = [LatticeVector([zero,zero,zero]),
                                  LatticeVector([half,zero,half])]
                self.lattrans = LatticeMatrix([[half, zero, -half],
                                               [zero, one, zero],
                                               [half, zero, half]])
            elif self.spacegroupsetting == 'C':
                # C-centered
                self.transvecs = [LatticeVector([zero,zero,zero]),
                                  LatticeVector([half,half,zero])]
                self.lattrans = LatticeMatrix([[half, -half, zero],
                                               [half, half, zero],
                                               [zero, zero, one]])
            elif self.HallSymbol in Hex2RhombHall or self.HallSymbol in Rhomb2HexHall:
                if abs(self.gamma - 120) < self.coordepsilon:
                    # rhombohedral from hexagonal setting
                    self.rhombohedral = True
                    self.transvecs = [LatticeVector([zero,zero,zero]),
                                      LatticeVector([third, 2*third, 2*third]),
                                      LatticeVector([2*third, third, third])]
                    self.lattrans = LatticeMatrix([[2*third, third, third],
                                                   [-third, third, third],
                                                   [-third, -2*third, third]])
                else:
                    self.transvecs = [LatticeVector([zero,zero,zero])]
                    self.lattrans = LatticeMatrix([[1, 0, 0],
                                                   [0, 1, 0],
                                                   [0, 0, 1]])
            else:
                self.transvecs = [LatticeVector([zero,zero,zero])]
                self.lattrans = LatticeMatrix([[1, 0, 0],
                                               [0, 1, 0],
                                               [0, 0, 1]])
            # Transform to primitive cell
            tmp = []
            for i in range(3):
                tmp.append(mvmult3(self.latticevectors,self.lattrans[i]))
            self.latticevectors = LatticeMatrix(tmp)
            # Improve precision again...
            for i in range(3):
                for j in range(3):
                    self.latticevectors[i][j] = improveprecision(self.latticevectors[i][j],self.coordepsilon)
        else:
            # If no reduction is to be done
            self.transvecs = [LatticeVector([zero,zero,zero])]
            self.lattrans = LatticeMatrix([[1, 0, 0],
                                          [0, 1, 0],
                                          [0, 0, 1]])

        # Find inverse lattice transformation matrix
        invlattrans = LatticeMatrix(minv3(self.lattrans))

        #################################
        #       SYMMETRY OPERATIONS     #
        #################################

        # If we reduce the cell, remove the symmetry operations that are the
        # same up to an induced lattice translation
        if self.primcell:
            if len(self.transvecs) > 1:
                redundant = set([])
                for op1 in self.symops:
                    for op2 in self.symops:
                        for vec in self.transvecs:
                            if op1.translation+vec == op2.translation:
                                if op1.rotation == op2.rotation:
                                    if op1.translation.length() < op2.translation.length():
                                        redundant.add(op2)
                self.symops -= redundant

        # Space group operations to cartesian representation
        lv = self.conventional_latticevectors()
        for op in self.symops:
            op.rotation = lv.transform(op.rotation)
            op.rotation = op.rotation.transform(minv3(lv))
            # transform translations
            op.translation = op.translation.transform(minv3(self.lattrans))

        # Test that the lattice vectors are invariant under all space group operations
        # If not, the data is given in some non-standard representation that presently
        # can't be handled.
        if self.crystal_system() == 'hexagonal' or self.crystal_system() == 'trigonal':
            # Hexagonal and trigonal as a special case... check that the hexagonal planes are in the ab plane
            for op in self.symops:
                if not (op.rotation[2] == Vector([0,0,1]) or op.rotation[2] == Vector([0,0,-1])):
                    raise SymmetryError("Lattice vectors do not fulfil the given symmetries of the lattice!\n"+
                                        "The cell is given in some non-standard setting presently not handled by the program.")
        else:
            for op in self.symops:
                if not op.translation.length() > self.compeps:
                    fails = False
                    for vec1 in lv:
                        transvec = vec1.transform(op.rotation)
                        if not (transvec == lv[0] or transvec == lv[1] or transvec == lv[2]
                                or transvec == -lv[0] or transvec == -lv[1] or transvec == -lv[2]):
                            fails = True
                    if fails:
                        raise SymmetryError("Lattice vectors do not fulfil the given symmetries of the lattice!\n"\
                                            "The cell is given in some non-standard setting presently not handled by the program.")

        #########################
        #    CELL GENERATION    #
        #########################
        # Atomic species and the number of each species. Site occupancies.
        for i in range(len(self.ineqsites)):
            # Set up atomdata
            self.atomdata.append([])
            self.atomdata[i].append(AtomSite(position=self.ineqsites[i], label=self.sitelabels[i]))
            # Add species and occupations to atomdata
            for k,v in self.occupations[i].items():
                self.atomdata[i][0].species[k] = v
                # Add charge state
                for k2,v2 in self.chargedict.items():
                    if k2.strip(string.punctuation+string.digits) == k:
                        self.atomdata[i][0].charges[k] = v2
            ## self.atomdata[i][0].charge = self.charges[i]
            # Determine if we have an alloy
            for element in self.occupations[i]:
                v = self.occupations[i][element]
                if abs(1-v) > occepsilon:
                    self.alloy = True

        # Make sites unique with array of occupation info
        removeindices = []
        # set up atomdata
        for i in range(len(self.atomdata)):
            for j in range(len(self.atomdata)-1,i,-1):
                if self.atomdata[i][0].position == self.atomdata[j][0].position:
                    # Add the dictionary of site j to that of site i and schedule index j for
                    # removal. If there is already an instance of the species on this site and
                    # the occupancy is different from 1, then add the occupancies (this happens
                    # when different valencies has been recorded).
                    # Now that the charge is stored, maybe this should be redone.
                    if self.atomdata[j][0].alloy:
                        for k in self.atomdata[j][0].species:
                            if k in self.atomdata[i][0].species:
                                v = self.atomdata[j][0].species[k] + self.atomdata[i][0].species[k]
                                self.atomdata[i][0].species[k] = v
                            else:
                                self.atomdata[i][0].species[k] = self.atomdata[j][0].species[k]
                    self.atomdata[i][0].charges.update(self.atomdata[j][0].charges)
                    removeindices.append(j)
                    # ...also fix self.occupations
                    self.occupations[i][list(self.occupations[j].keys())[0]] = list(self.occupations[j].values())[0]
        # Remove duplicate elements
        removeindices = list(set(removeindices))
        removeindices.sort(reverse=True)
        for i in removeindices:
            self.atomdata.pop(i)
            self.ineqsites.pop(i)
            self.occupations.pop(i)

        # Work out all sites in the cell for atomdata/atomset
        for a in self.atomdata:
            for op in self.symops:
                # position expression string
                posexpr = [s for s in op.eqsite]
                for k in range(3):
                    # position expression string, replacing x,y,z with numbers
                    posexpr[k] = posexpr[k].replace('x',str(a[0].position[0]))
                    posexpr[k] = posexpr[k].replace('y',str(a[0].position[1]))
                    posexpr[k] = posexpr[k].replace('z',str(a[0].position[2]))
                position = LatticeVector([safe_matheval(pos) for pos in posexpr])
                b = AtomSite(position=position,species=a[0].species,charges=a[0].charges,label=a[0].label)
                self.atomset.add(b)
                append = True
                for site in a:
                    for vec in self.transvecs:
                        t = vec + b.position
                        if site.position == t:
                            append=False
                            break
                    if not append:
                        break
                if append:
                    a.append(b)
        # Transform positions. Note that atomdata and atomset alias the same data,
        # so we only transform once.
        for a in self.atomdata:
            for b in a:
                b.position = LatticeVector(mvmult3(invlattrans,b.position))

        # Weed out remaining duplicates. A weird special case that arises when
        # different symmetry equivalent sites where listed in the input file.
        # Attempts to handle this on the fly from the beginning made a complete
        # mess of the alloy handling...
        removeindices = set([])
        for i in range(len(self.atomdata)):
            for j in range(len(self.atomdata[i])):
                for k in range(i+1,len(self.atomdata)):
                    for l in range(len(self.atomdata[k])):
                        if self.atomdata[i][j].position == self.atomdata[k][l].position:
                            removeindices.add((k,l))
        removeindices = list(removeindices)
        removeindices.sort(reverse=True)
        for i,j in removeindices:
            self.atomdata[i].pop(j)
        # Check if any type is now completely empty
        removeindices = []
        for i in range(len(self.atomdata)):
            if len(self.atomdata[i]) == 0:
                removeindices.append(i)
        removeindices.sort(reverse=True)
        for i in removeindices:
            self.atomdata.pop(i)

        ######################
        #    MISCELLANEOUS   #
        ######################
        # Chemical content dictionary
        for a in self.atomdata:
            for b in a:
                for k,v in b.species.items():
                    if k in self.ChemicalComposition:
                        n = self.ChemicalComposition[k]
                        self.ChemicalComposition[k] = v+n
                    else:
                        self.ChemicalComposition[k] = v
        if not self.alloy:
            L = list(self.ChemicalComposition.values())
            divisor = reduce(gcd,L)
            for k,v in self.ChemicalComposition.items():
                self.ChemicalComposition[k] = v/divisor
        # Number of atoms
        self.numberOfAtoms = self.natoms()
        # Set flag and return the CrystalStructure in the conventional setting
        self.initialized = True
        return self

    def transformCell(self, transformation):
        """
        Applies transformation to bravais lattice vectors (and symmetry operations).
        Only transformations involving rotations and an overall rescaling of the cell are allowed.
        """
        r = LatticeMatrix(transformation)
        fac = pow(abs(det3(r)),float(1)/3)
        # Check that the transformation does not skew the cell.
        oldanglen = set([CellFloat(self.latticevectors[0].angle(self.latticevectors[1])),
                         CellFloat(self.latticevectors[0].angle(self.latticevectors[2])),
                         CellFloat(self.latticevectors[1].angle(self.latticevectors[2])),
                         CellFloat(self.latticevectors[0].length()),
                         CellFloat(self.latticevectors[1].length()),
                         CellFloat(self.latticevectors[2].length())])
        t = LatticeMatrix(mmmult3(self.latticevectors,r))
        newanglen = set([CellFloat(t[0].angle(t[1])),
                         CellFloat(t[0].angle(t[2])),
                         CellFloat(t[1].angle(t[2])),
                         CellFloat(t[0].length()/fac),
                         CellFloat(t[1].length()/fac),
                         CellFloat(t[2].length()/fac)])
        if oldanglen==newanglen or self.force:
            self.latticevectors = t
            self.lengthscale /= fac
            # Transform symmetry operations
            newsymops = set([])
            for op in self.symops:
                o = copy.copy(op)
                o.rotation = LatticeMatrix(mmmult3(mmmult3(minv3(r),o.rotation),r))
                o.improveprecision()
                newsymops.add(o)
            self.symops = newsymops
            if oldanglen!=newanglen and self.force:
                sys.stderr.write("***Error: The transformation matrix skews the lattice. Only combinations of \n"+
                                 "          rotations and rescaling of the whole cell are allowed.")
        else:
            raise CellError("The transformation matrix skews the lattice. Only combinations of "+
                            "rotations and rescaling of the whole cell are allowed.")

    def getSuperCell(self, supercellmap, vacuum, prevactransvec, postvactransvec=[.0,.0,.0], sort=""):
        """
        Returns a supercell based on the input supercell map, vacuum layers and translation vector.
        The cell must have been initialized prior to calling getSuperCell.

        The cell will be padded with some number of original unit cells of vacuum
        by simple rescaling of the lattice vectors and positions. This is controlled by 'vacuum'.

        Prior to addition of vacuum, all coordinates will be translated by 'prevactransvec',
        which is given in units of the original lattice vectors. After the addition of vacuum,
        all coordinates are translated by 'postvactransvec' (given in units of the final lattice).
        """

        # Sanity checks
        if not self.initialized:
            raise CellError("The unit cell must be initialized before a supercell can be generated.")
        if len(vacuum) != 3: #or vacuum[0] < 0 or vacuum[1] < 0 or vacuum[2] < 0:
            raise CellError("The vacuum padding must be an array of three numbers >= 0.")

        # Map matrix
        try:
            mapmatrix = LatticeMatrix([[supercellmap[0],0,0],[0,supercellmap[1],0],[0,0,supercellmap[2]]])
        except:
            try:
                mapmatrix = supercellmap
            except:
                raise CellError("The supercell map must be a vector or a matrix.")
        # Inverse of map matrix.
        try:
            invmapmatrix = LatticeMatrix(minv3(mapmatrix))
        except:
            raise CellError("The supercell map must be invertible.")
        volratio = abs(det3(mapmatrix))
        # Volume ratio must be a non-zero integer.
        if abs(volratio-round(volratio,0)) > self.compeps:
            raise CellError("The determinant of the supercell map must be a non-zero integer.")
            ## sys.stderr.write("***Warning: The determinant of the supercell map is a non-integer.\n")
            ## sys.stderr.write("            If you did not expect this warning, immediately stop to\n")
            ## sys.stderr.write("            rethink what you are doing.\n")

        # New latticevectors from supercell map.
        t = mmmult3(mapmatrix,self.latticevectors)
        self.latticevectors = LatticeMatrix(t)
        invlatvects = minv3(self.latticevectors)

        # Set up new translation group (in new lattice vector coordinates).
        # Determine limits for translation vector search
        # (adapted from John Wills' cellgen program).
        M = mapmatrix
        #
        lo = []
        up = []
        for i in range(3):
            sumset = set([])
            for j in range(3):
                sumset.add(int(M[i][j]))
            sumset.add(int(M[i][0])+int(M[i][1]))
            sumset.add(int(M[i][0])+int(M[i][2]))
            sumset.add(int(M[i][1])+int(M[i][2]))
            sumset.add(int(M[i][0])+int(M[i][1])+int(M[i][2]))
            sumset.add(int(M[i][0])-int(M[i][1]))
            sumset.add(int(M[i][0])-int(M[i][2]))
            sumset.add(int(M[i][1])-int(M[i][2]))
            sumset.add(int(M[i][0])-int(M[i][1])-int(M[i][2]))
            lo.append(min(sumset)-1)  # Don't really understand why I need to add/subtract
            up.append(max(sumset)+1)  # 1 here... but things sometimes fail if I don't.
        # Translation vector search
        newtranslations = set([])
        for k in range(lo[0], up[0]+1):
            for j in range(lo[1], up[1]+1):
                for i in range(lo[2], up[2]+1):
                    t = LatticeVector(mvmult3(invmapmatrix,[k,j,i])) # convert to new lattice coords
                    newtranslations.add(t)
        # Remove identity translation.
        newtranslations.remove(LatticeVector([0,0,0]))

        # Transform original coordinates to new basis.
        for a in self.atomdata:
            for b in a:
                b.position = LatticeVector(mvmult3(invmapmatrix,b.position))
        for op in self.symops:
            op.translation = LatticeVector(mvmult3(invmapmatrix,op.translation))

        # Operate with new translation group on coordinates to generate all positions
        newsites = []
        i = 0
        for a in self.atomdata:
            newsites.append([])
            for b in a:
                for translation in newtranslations:
                    position = LatticeVector(b.position + translation)
                    t = AtomSite(position=b.position,species=b.species,charges=b.charges)
                    t.position = position
                    newsites[i].append(t)
            i += 1
        i = 0
        for a in newsites:
            for b in a:
                self.atomdata[i].append(b)
                self.atomset.add(b)
            i += 1

        # Move all atoms by prevactransvec
        if reduce(lambda x,y: x+y, prevactransvec) != 0:
            for i in range(len(self.atomdata)):
                for j in range(len(self.atomdata[i])):
                    for k in range(3):
                        self.atomdata[i][j].position[k] = self.atomdata[i][j].position[k] + prevactransvec[k]

        # Put stuff back in cell
        for a in self.atomdata:
            for b in a:
                b.position.intocell()

        # Put positions in cartesian coordinates for vacuum generation
        for a in self.atomdata:
            for b in a:
                b.position = Vector(mvmult3(self.latticevectors,b.position))
        # New latticevectors after vacuum padding
        vacuummapmatrix = LatticeMatrix([[1,0,0],[0,1,0],[0,0,1]])
        if reduce(lambda x,y: x+y, vacuum) > 0:
            # add the given number of unit cell units along the lattice vectors
            for j in range(len(vacuum)):
                for i in range(len(self.latticevectors[j])):
                    self.latticevectors[j][i] = self.latticevectors[j][i] + self.latticevectors[j][i]*vacuum[j]
                vacuummapmatrix[j][j] = vacuummapmatrix[j][j] + vacuum[j]
        # Remap coordinates after padding
        invlatvect = LatticeMatrix(minv3(self.latticevectors))
        for a in self.atomdata:
            for b in a:
                b.position = LatticeVector(mvmult3(invlatvect, b.position))

        # Move all atoms by postvactransvec
        if reduce(lambda x,y: x+y, postvactransvec) != 0:
            for i in range(len(self.atomdata)):
                for j in range(len(self.atomdata[i])):
                    for k in range(3):
                        self.atomdata[i][j].position[k] = self.atomdata[i][j].position[k] + postvactransvec[k]

        ############ New space group operations ############
        # Only sort out space group information for diagonal map matrix. !SHOULD BE FIXED GENERALLY!
        eps = self.compeps
        diagonal = abs(mapmatrix[0][1]) < eps and abs(mapmatrix[0][2]) < eps and abs(mapmatrix[1][2]) < eps and \
                   abs(mapmatrix[1][0]) < eps and abs(mapmatrix[2][0]) < eps and abs(mapmatrix[2][1]) < eps
        if diagonal:
            # Multiply group by new translation group
            newops = []
            i = 0
            for vec in newtranslations:
                for op in self.symops:
                    newops.append(SymmetryOperation())
                    newops[i].rotation = op.rotation
                    newops[i].translation = vec + op.translation
                    i += 1
            for op in newops:
                self.symops.add(op)

            # Weed out rotations that are broken by supercell map
            lv = self.latticevectors
            removeset = set([])
            # Ugly set of if's and special cases
            # THIS WILL NOT WORK WITH GENERAL SUPERCELL MAP MATRIX
            if self.crystal_system()=="hexagonal" or (self.crystal_system()=="trigonal" and not self.primcell):
                if abs(lv[0].length()-lv[1].length()) < lv.compeps:
                    # if a and b are still the same, no rotation symmetry is broken
                    pass
                else:
                    # if a and b are different, all rotation symmetries except inversion are broken
                    e = SymmetryOperation(["x","y","z"])
                    i = SymmetryOperation(["-x","-y","-z"])
                    for op in self.symops:
                        if op.rotation == e.rotation or op.rotation == i.rotation:
                            pass
                        else:
                            removeset.add(op)
            elif self.crystal_system()=="trigonal" and self.primcell:
                # if any latticevector has different length, all symmetries except inversion are broken
                if abs(lv[0].length()-lv[1].length()) < lv.compeps and \
                   abs(lv[1].length()-lv[2].length()) < lv.compeps and \
                   abs(lv[0].length()-lv[2].length()) < lv.compeps:
                    pass
                else:
                    e = SymmetryOperation(["x","y","z"])
                    i = SymmetryOperation(["-x","-y","-z"])
                    for op in self.symops:
                        if op.rotation == e.rotation or op.rotation == i.rotation:
                            pass
                        else:
                            removeset.add(op)
            else:
                for op in self.symops:
                    for vec in lv:
                        t = Vector(mvmult3(op.rotation,vec))
                        r = Vector([-u for u in t])
                        # Symmetry operation OK if it maps a lattice vector into one of the other lattice vectors
                        equivalent = t == lv[0] or t == lv[1] or t == lv[2] or \
                                     r == lv[0] or r == lv[1] or r == lv[2]
                        if not equivalent:
                            removeset.add(op)
                            continue
            # Weed out translations broken by the vacuum
            for op in self.symops:
                # check if vacuum padding destroys this translation
                t = op.translation
                for i in range(3):
                    if abs(t[i]) > self.compeps and abs(vacuum[i]) > self.compeps:
                        removeset.add(op)
            # Remove broken symmetries
            for op in self.symops:
                for vec in lv:
                    t = Vector(mvmult3(op.rotation,vec))
        else:
            # Otherwise just keep identity
            self.symops = set([SymmetryOperation(['x','y','z'])])


        # Sort the atomic positions if requested.
        if sort != "":
            # remove previous ordering
            tempdata = []
            i = 0
            for a in self.atomdata:
                for b in a:
                    tempdata.append([])
                    tempdata[i].append(b)
                    i += 1
            self.atomdata = tempdata
            # Identify and sort by z-layers
            if sort == "zlayer":
                # sort atoms by z-coordinate
                self.atomdata.sort(key = lambda a: a[0].position.transform(self.latticevectors)[2])
                #
            elif len(sort) == 3:
                # check if the string contains only 'x', 'y' or 'z'
                allbutxyz = string.printable.replace("x","").replace("y","").replace("z","")
                # check if the string contains only '1', '2' or '3'
                allbut123 = string.printable.replace("1","").replace("2","").replace("3","")
                # dummy table to work in python < 2.6
                table = str.maketrans("a","a")
                if len(string.translate(sort,table,allbutxyz)) == 3:
                    # Sort atoms by cartesian coordinate
                    sortnum = string.translate(sort,str.maketrans("xyz","012"))
                    for i in sortnum:
                        self.atomdata.sort(key = lambda a: a[0].position.transform(self.latticevectors)[int(i)])
                elif len(string.translate(sort,table,allbut123)) == 3:
                    # sort atoms by lattice coordinates
                    for i in sort:
                        self.atomdata.sort(key = lambda a: a[0].position[int(i)-1])
        self.supercell = True
        self.numberOfAtoms = self.natoms()
        return self

    # Get lattice information from CIF block
    def getFromCIF(self, cifblock=None):
        ################################
        # Get space group information  #
        ################################
        # _space_group is the primary choice, so if both _symmetry and _space_group
        # are present, _symmetry will be overwritten
        for spgrnrid in ['_symmetry_Int_Tables_number','_space_group_IT_number']:
            try:
                self.spacegroupnr = int(cifblock[spgrnrid])
            except:
                pass
        for hallid in ['_symmetry_space_group_name_Hall','_space_group_name_Hall']:
            try:
                self.HallSymbol=cifblock[hallid]
            except:
                pass
        for HMid in ['_symmetry_space_group_name_H-M','_space_group_name_H-M_alt']:
            try:
                # self.HMSymbol=cifblock[HMid].translate(str.maketrans("", ""),str.whitespace)
                self.HMSymbol=cifblock[HMid].replace(" ", "")
                # self.HMSymbol=cifblock[HMid]
            except:
                pass

        # Force correct case for space group symbols
        if self.HMSymbol != "":
            self.HMSymbol = self.HMSymbol[0].upper()+self.HMSymbol[1:].lower()
            if self.HMSymbol[-1] == 'r':
                tmp = list(self.HMSymbol)
                tmp[-1] = 'R'
                self.HMSymbol = "".join(tmp)
            if self.HMSymbol[-1] == 'h':
                tmp = list(self.HMSymbol)
                tmp[-1] = 'H'
                self.HMSymbol = "".join(tmp)
            if self.HMSymbol[-1] == 's':
                tmp = list(self.HMSymbol)
                tmp[-1] = 'S'
                self.HMSymbol = "".join(tmp)
            if self.HMSymbol[-1] == 'z':
                tmp = list(self.HMSymbol)
                tmp[-1] = 'Z'
                self.HMSymbol = "".join(tmp)
        if self.HallSymbol != "":
            if self.HallSymbol[0] == "-":
                self.HallSymbol = "-"+self.HallSymbol[1].upper()+self.HallSymbol[2:].lower()
            else:
                self.HallSymbol = self.HallSymbol[0].upper()+self.HallSymbol[1:].lower()

        # Get symmetry equivalent positions (space group operations).
        eqsites = None
        for symopid in ['_symmetry_equiv_pos_as_xyz','_space_group_symop_operation_xyz']:
            try:
                eqsitedata = cifblock.GetLoop(symopid)
                try:
                    eqsitestrs = eqsitedata.get(symopid)
                    # This if fixes a funny exception that can occur for the P1 space group.
                    if type(eqsitestrs) == str:
                        eqsitestrs = [eqsitestrs]
                    eqsites = []
                    for i in range(len(eqsitestrs)):
                        tmp = eqsitestrs[i].split(',')
                        eqsites.append([])
                        for j in range(len(tmp)):
                            eqsites[i].append(tmp[j].strip().lower())
                except KeyError:
                    self.symops = None
            except KeyError:
                self.symops = None

        # Only Hall symbols are used internally.
        if self.HallSymbol == "" or self.HallSymbol == "?" or self.HallSymbol == "." or not self.HallSymbol in Hall2HM:
            if self.HMSymbol == "" or self.HMSymbol == "?" or self.HMSymbol == ".":
                if 0 < self.spacegroupnr <= 230:
                    try:
                        self.HallSymbol = Number2Hall[self.spacegroupnr]
                    except:
                        raise SymmetryError("Found neither Hall nor H-M symbol and space group %i does not have a unique setting."%self.spacegroupnr)
                else:
                    if self.force:
                        sys.stderr.write("***Warning: CIF file contains neither space group symbols nor space group number.\n")
                        sys.stderr.write("            Defaulting to P1. Check results carefully!\n")
                        self.HallSymbol = "P 1"
                    else:
                        raise SymmetryError("CIF file contains neither space group symbols nor space group number.")
            try:
                self.HallSymbol = HM2Hall[self.HMSymbol]
            except:
                self.HallSymbol = "Unknown"

        # space group setting
        if self.HallSymbol[0] == "-":
            self.spacegroupsetting = self.HallSymbol[1]
        else:
            self.spacegroupsetting = self.HallSymbol[0]

        # Set space group number and H-M symbol, if not in file.
        if self.spacegroupnr < 1 or self.spacegroupnr > 230:
            self.spacegroupnr = Hall2Number[self.HallSymbol]
        if self.HMSymbol == "":
            self.HMSymbol = Hall2HM[self.HallSymbol]

        # If no symmetry operations in file, get internally stored.
        if type(eqsites) == type(None):
            eqsites = SymOpsHall[self.HallSymbol]
        else:
            try:
                # Check if symmetry operations are consistent with current space group
                if len(eqsites) != len(SymOpsHall[self.HallSymbol]):
                    if self.force:
                        sys.stderr.write("***Warning: Number of space group operations (%3i) is inconsistent "%len(eqsites)\
                                         +"with the given space group (%s).\n"%self.HMSymbol)
                    else:
                        raise SymmetryError("Number of space group operations (%3i) is inconsistent "%len(eqsites)\
                                            +"with the given space group (%s)."%self.HallSymbol)
            except:
                sys.stderr.write("***Warning: Space group operation check failed for Hall symbol %s (H-M symbol %s).\n"%(self.HallSymbol,self.HMSymbol))
        # Define the set of space group operations.
        self.symops = set([])
        for site in eqsites:
            self.symops.add(SymmetryOperation(site))

        #######################
        #    Get cell data    #
        #######################
        try:
            # Set initial crystal parameters
            self.ainit     = float(removeerror(cifblock['_cell_length_a']))
            self.binit     = float(removeerror(cifblock['_cell_length_b']))
            self.cinit     = float(removeerror(cifblock['_cell_length_c']))
            self.alphainit = float(removeerror(cifblock['_cell_angle_alpha']))
            self.betainit  = float(removeerror(cifblock['_cell_angle_beta']))
            self.gammainit = float(removeerror(cifblock['_cell_angle_gamma']))
            self.coainit = self.cinit / self.ainit
            self.boainit = self.binit / self.ainit
        except:
            self.ainit = 0
            self.binit = 0
            self.cinit = 0
            self.alphainit = 0
            self.betainit = 0
            self.gammainit = 0
            raise CellError("Unable to read crystallographic parameters")
        # Set crystal parameters to be used (may be changed)
        self.a = self.ainit
        self.b = self.binit
        self.c = self.cinit
        self.alpha = self.alphainit
        self.beta  = self.betainit
        self.gamma = self.gammainit
        self.coa = self.c / self.a
        self.boa = self.b / self.a

        # Get info on atom positions
        try:
            # Lattice coordinates
            tmpdata = cifblock.GetLoop('_atom_site_fract_x')
        except:
            try:
                # Cartesian coordinates
                tmpdata = cifblock.GetLoop('_atom_site_Cartn_x')
            except:
                raise PositionError("Unable to find positions.")
            self.cartesianInput = True
            # Try to get transformation matrix to interpret cartesian positions
            try:
                t11 = cifblock.get('_atom_sites_Cartn_tran_matrix_11')
                t12 = cifblock.get('_atom_sites_Cartn_tran_matrix_12')
                t13 = cifblock.get('_atom_sites_Cartn_tran_matrix_13')
                t21 = cifblock.get('_atom_sites_Cartn_tran_matrix_21')
                t22 = cifblock.get('_atom_sites_Cartn_tran_matrix_22')
                t23 = cifblock.get('_atom_sites_Cartn_tran_matrix_23')
                t31 = cifblock.get('_atom_sites_Cartn_tran_matrix_13')
                t32 = cifblock.get('_atom_sites_Cartn_tran_matrix_23')
                t33 = cifblock.get('_atom_sites_Cartn_tran_matrix_33')
                self.cart_trans_matrix = [[float(t11),float(t12),float(t13)],
                                          [float(t21),float(t22),float(t23)],
                                          [float(t31),float(t32),float(t33)]]
            except:
                if self.force:
                    sys.stderr.write("***Warning: Cartesian coordinates in CIF, but no transformation matrix given.\n")
                    sys.stderr.write("            Using choice implied by the default lattice vectors. Check results carefully!\n")
                else:
                    raise PositionError("Cartesian coordinates in CIF, but no transformation matrix given.")
            # Try to get transformation matrix to interpret cartesian positions
            try:
                t1 = cifblock.get('_atom_sites_Cartn_tran_vector_1')
                t2 = cifblock.get('_atom_sites_Cartn_tran_vector_2')
                t3 = cifblock.get('_atom_sites_Cartn_tran_vector_3')
                self.cart_trans_vector = Vector([float(t1),float(t2),float(t3)])
            except:
                if self.force:
                    sys.stderr.write("***Warning: Cartesian coordinates in CIF, but no translation vector given.\n")
                    sys.stderr.write("            Using [0,0,0]. Check results carefully!\n")
                    self.cart_trans_vector = Vector([0., 0., 0.])
                else:
                    raise PositionError("Cartesian coordinates in CIF, but no translation vector given.")
        # Positions
        removedefective = set([])
        try:
            if self.cartesianInput:
                sitexer = tmpdata.get('_atom_site_Cartn_x')
                siteyer = tmpdata.get('_atom_site_Cartn_y')
                sitezer = tmpdata.get('_atom_site_Cartn_z')
            else:
                sitexer = tmpdata.get('_atom_site_fract_x')
                siteyer = tmpdata.get('_atom_site_fract_y')
                sitezer = tmpdata.get('_atom_site_fract_z')
            if (type(sitexer) == None or type(siteyer) == None or type(sitezer) == None or \
                '?' in sitexer or '?' in siteyer or '?' in sitezer or \
                '.' in sitexer or '.' in siteyer or '.' in sitezer):
                if self.force:
                    sys.stderr.write("***Warning: Positions are missing, generating cell with the remaining atoms anyway.\n")
                    # Remove defective sites from arrays.
                    for i in range(len(sitexer)):
                        if (sitexer[i] == '?' or siteyer[i] == '?' or sitezer[i] == '?' or \
                            sitexer[i] == '.' or siteyer[i] == '.' or sitezer[i] == '.'):
                            removedefective.add(i)
                else:
                    raise PositionError("Positions not found for one or more species.")
        except KeyError:
            raise PositionError("Positions not found for one or more species.")

        # Element names
        elementsymbs = tmpdata.get('_atom_site_type_symbol')
        # print(elementsymbs)
        if elementsymbs is None or '?' in elementsymbs or '.' in elementsymbs:
            elementsymbs = tmpdata.get('_atom_site_label')
            if type(elementsymbs) == None:
                # Fill up with question marks if not found
                sys.stderr.write("***Warning: Could not find element names.\n")
                elementsymbs = ["??" for site in sitexer]

        # Site labels from _atom_site_label
        self.sitelabels = tmpdata.get('_atom_site_label')
        if type(self.sitelabels) == None:
            # Fill up with question marks if not found
            if not self.quiet:
                sys.stderr.write("Could not find site labels.\n")
            self.sitelabels = ["" for site in sitexer]

        # Find charge state
        self.chargedict = dict([])
        self.charges = []
        try:
            # This is usually encoded in _atom_site_type_symbol, but we go by _atom_type_oxidation_number first.
            tmpdata2 = cifblock.GetLoop('_atom_type_oxidation_number')
            symbs = tmpdata2.get('_atom_type_symbol')
            oxnums = tmpdata2.get('_atom_type_oxidation_number')
            for element in elementsymbs:
                i = 0
                for symb in symbs:
                    if symb == element:
                        self.chargedict[element] = Charge(oxnums[i])
                        self.charges.append(Charge(oxnums[i]))
                    i+=1
        except:
            # Try _atom_site_type_symbol
            try:
                oxnums = [elem.strip(string.letters) for elem in elementsymbs]
                for i in range(len(oxnums)):
                    if oxnums[i] == '':
                        raise ValueError("Empty string found.")
                    if oxnums[i].strip(string.digits) == '+':
                        self.charges.append(Charge(float(oxnums[i].strip(string.punctuation))))
                    elif oxnums[i].strip(string.digits) == '-':
                        self.charges.append(Charge(-float(oxnums[i].strip(string.punctuation))))
                    self.chargedict[elementsymbs[i]] = self.charges[i]
            except:
                # if all else fails, just fill up with zeros
                self.charges = [Charge(0) for element in elementsymbs]
                for element in elementsymbs:
                    self.chargedict[element] = Charge(0)

        # Try to get number of atoms from symmetry multiplicities (if present)
        try:
            tmpdata = cifblock.GetLoop('_atom_site_symmetry_multiplicity')
            i = 0
            for t in tmpdata:
                i += int(t[0])
            self.numberOfAtoms = i
        except:
            pass
        # Remove stuff (usually charge state specification) from element symbol strings
        self.elements = []
        i = 0
        for elem in elementsymbs:
            self.elements.append(elem.strip(string.punctuation+string.digits))
            # Make it ?? if there was nothing left after removing junk
            if self.elements[i] == "":
                self.elements[i] = "??"
            i += 1
        # Make element name start with capital and then have lower case letters
        self.elements[:] = [element[0].upper()+element[1:].lower() for element in self.elements]
        for element in self.elements:
            if not element in ElementData().elementnr:
                sys.stderr.write("***Warning: "+element+" is not a chemical element.\n")
        # Find occupancies
        try:
            siteoccer = tmpdata.get('_atom_site_occupancy')
        except KeyError:
            raise PositionError("Error reading site occupancies.")
        if siteoccer == None or '?' in siteoccer or '.' in siteoccer:
            if not self.quiet:
                sys.stderr.write("***Warning : Site occupancies not found, assuming all occupancies = 1.\n")
            siteoccer = []
            for site in self.elements:
                siteoccer.append("1.0")
        #
        self.ineqsites = []
        self.occupations = []
        for i in range(len(self.elements)):
            self.ineqsites.append([])
            # Remove error estimates from coordinates
            for j in sitexer[i], siteyer[i], sitezer[i]:
                try:
                    self.ineqsites[i].append(float(removeerror(j)))
                except:
                    if self.force:
                        removedefective.add(i)
                        sys.stderr.write("***Warning : Invalid atomic position value : "+j+"\n")
                    else:
                        raise PositionError("Invalid atomic position value : "+j)
            # Improve precision
            self.ineqsites[i] = Vector(self.ineqsites[i])
            # dictionary of elements and occupancies
            k = self.elements[i]
            try:
                v = float(removeerror(siteoccer[i]))
            except ValueError:
                v = 1.0
            if abs(v-1.0) > 1e-6:
                self.alloy = True
            self.occupations.append({ k : v })

        # If there is a set of defective sites, remove them if forced.
        if removedefective and self.force:
            removedefective = list(removedefective)
            removedefective.sort(reverse=True)
            for i in removedefective:
                try:
                    self.ineqsites.pop(i)
                    self.occupations.pop(i)
                except:
                    pass


    def printCell(self,printsym=False,printinput=False,printcart=False,printdigits=8,printcharges=False):
        # format string for outputting decimal numbers to screen
        decpos = printdigits + 3
        decform = "%"+str(decpos)+"."+str(decpos-4)+"f"
        threedecs = " "+decform+" "+decform+" "+decform
        fourdecs = " "+decform+" "+decform+" "+decform+" "+decform
        # Pretty printing in columns that need to have variable width
        # w1 = width of the atomic species column
        # w2 = width of a decimal column
        # w3 = width of the occupancy column
        # w4 = width of the charge state column
        if self.alloy:
            w1 = 0
            w3 = 0
            w4 = 0
            # Find atom and occupation column widths
            for a in self.atomdata:
                for b in a:
                    tmpstring1 = ""
                    tmpstring2 = ""
                    tmpstring3 = ""
                    for k,v in b.species.items():
                        tmpstring1 += k+"/"
                        tmpstring2 += str(v).rstrip("0.")+"/"
                        # charge output
                        for k2,v2 in self.chargedict.items():
                            if k2.strip(string.punctuation+string.digits) == k:
                                tmpstring3 += str(v2)+"/"
                    tmpstring1 = tmpstring1.rstrip("/")
                    tmpstring2 = tmpstring2.rstrip("/")
                    tmpstring3 = tmpstring3.rstrip("/")
                    w1 = max(w1,len(tmpstring1))
                    w3 = max(w3,len(tmpstring2))
                    w4 = max(w4,len(tmpstring3))
            # small aesthetic adjustment
            w1 = w1 + 1
            w3 = w3 + 2
            w4 = max(w4 + 2, 8)
        else:
            w1 = 5
            w2 = decpos
            w3 = 0
            # width of charge column
            if printcharges:
                w4 = 7
            else:
                w4 = 0
        # Start output
        print("Bravais lattice vectors :")
        # Site header
        siteheader = "Atom".ljust(w1)+" "
        if printcart:
            transmtx = []
            for i in range(3):
                transmtx.append([])
                for j in range(3):
                    transmtx[i].append(self.latticevectors[i][j]*self.a)
                i += 1
            for i in ["x","y","z"]:
                siteheader += i.rjust(decpos)+" "
        else:
            transmtx = [[1, 0, 0],
                        [0, 1, 0],
                        [0, 0, 1]]
            for i in ["a1","a2","a3"]:
                siteheader += i.rjust(decpos)+" "
        if self.alloy:
            if w3 > 13:
                siteheader += "occupancies".rjust(w3)
            else:
                siteheader += "occ.".rjust(w3)
        if printcharges:
            siteheader += " "+"charge".rjust(w4)
        #
        if printcart:
            fact = self.lengthscale
        else:
            fact = 1
        formatstring = ""
        for i in range(3):
            formatstring = formatstring+decform+" "
        for i in range(3):
            print(formatstring % (self.latticevectors[i][0]*fact, self.latticevectors[i][1]*fact, self.latticevectors[i][2]*fact))
        # Print out all sites
        tmpstring = "All sites, "
        if printcart:
            tmpstring += "(cartesian coordinates):"
        else:
            tmpstring += "(lattice coordinates):"
        print(tmpstring)
        print(siteheader)
        for a in self.atomdata:
            for b in a:
                spcsstring = ""
                occstring = ""
                chargestring = ""
                for k,v in b.species.items():
                    spcsstring += k+"/"
                    occstring += str(v).rstrip("0.")+"/"
                    # charge output
                    for k2,v2 in self.chargedict.items():
                        if k2.strip(string.punctuation+string.digits) == k:
                            chargestring += str(v2)+"/"
                spcsstring = spcsstring.rstrip("/")
                occstring = occstring.rstrip("/")
                chargestring = chargestring.rstrip("/")
                v = mvmult3(transmtx,b.position)
                tmpstring = spcsstring.ljust(w1)+threedecs%(v[0],v[1],v[2])
                if self.alloy:
                    tmpstring += " "+occstring.rjust(w3)
                if printcharges:
                    tmpstring += " "+chargestring.rjust(w4)
                print(tmpstring)



################################################################################################
class ReferenceData:
    """
    Container class for a set of reference data strings.
    Also contains the getFromCIF method to obtain the data from a CIF block.

    database        : database from which the data was obtained
    databasecode    : some identifier used by the database
    databasestring  : a ready formatted string describing the database info.
    compound        : long compound name
    cpd             : short compound name
    authors         : list of strings with the author names
    authorstring    : string with author names formatted as:
                       single author  -  authors name
                       two authors    -  first author and second author
                       > two authors  -  first author et al.
    journal         :\
    volume          : |
    firstpage       :  - self-explanatory
    lastpage        : |
    year            :/

    Methods:
    getFromCIF      : Get reference data from a CIF block
    journalstring   : journal, volume firstpage-lastpage (year)
    referencestring : authorstring, journalstring
    bibtexref       : output a string for bibtex

    Various attempts at identifying the data are made and if they all fail
    an empty string is returned.

    """
    def __init__(self):
        self.database = ""
        self.databasecode = ""
        self.databasestring = ""
        self.compound = ""
        self.cpd = ""
        self.ChemicalComposition = dict([])
        self.authors = []
        self.authorstring = ""
        self.title = ""
        self.journal = ""
        self.volume = ""
        self.firstpage = ""
        self.lastpage = ""
        self.year = ""
        # Some known databases
        self.databasenames = {
            'CAS'  : 'Chemical Abstracts',
            'CSD'  : 'Cambridge Structural Database',
            'ICSD' : 'Inorganic Crystal Structure Database',
            'MDF'  : 'Metals Data File (metal structures)',
            'NBS'  : '(NIST) Crystal Data Database',
            'PDB'  : 'Protein Data Bank',
            'PDF'  : 'Powder Diffraction File (JCPDS/ICDD)',
            'COD'  : 'Crystallography Open Database'
            }
        self.databaseabbr = {
             'Chemical Abstracts'                   : 'CAS',
             'Cambridge Structural Database'        : 'CSD',
             'Inorganic Crystal Structure Database' : 'ICSD',
             'Metals Data File (metal structures)'  : 'MDF',
             '(NIST) Crystal Data Database'         : 'NBS',
             'Protein Data Bank'                    : 'PDB',
             'Powder Diffraction File (JCPDS/ICDD)' : 'PDF',
             'Crystallography Open Database'        : 'COD'
            }

    def bibtexref(self):
        string = "@article{"
        # Guess what is the first authors last name
        tmp = self.authors[0].replace(" ","")
        tmp = tmp.split(',')
        deletelist = []
        for i in range(len(tmp)):
            tmp[i] = tmp[i].split('.')
            if max([len(t) for t in tmp[i]]) < 2:
                deletelist.append(i)
        deletelist.sort(reverse=True)
        for i in deletelist:
            tmp.pop(i)
        tmp = [item for sublist in tmp for item in sublist]
        # Add label consisting of first authors last name and the year
        string += tmp[-1]+str(self.year)+",\n"
        # Add authors
        string += "author = {"
        for author in self.authors:
            string += author+" and "
        string = string[0:len(string)-5]
        string += "},\n"
        # Add title
        if len(self.title) > 0:
            string += "title = {"+self.title+"},\n"
        # Add journal
        if len(self.journal) > 0:
            string += "journal = {"+self.journal+"},\n"
        # Add volume
        if len(self.volume) > 0:
            string += "volume = {"+self.volume+"},\n"
        # Add page(s)
        if len(self.firstpage) > 0:
            string += "pages = {"+self.firstpage+"--"+self.lastpage
            string = string.rstrip("-")+"},\n"
        # Add year
        if len(self.year) > 0:
            string += "year = {"+self.year+"},\n"
        string += "}\n"
        return string

    def journalstring(self):
        try:
            if not (self.journal == "" and self.volume == "" and self.firstpage=="" and self.year==""):
                journalstring = self.journal
                journalstring += " "+self.volume
                journalstring += ", "+self.firstpage+"-"+self.lastpage
                journalstring += " ("+self.year+")"
            else:
                journalstring = "No journal information"
        except:
            journalstring = "Failed to create journal string"
        return journalstring

    def referencestring(self):
        try:
            if self.authorstring == "":
                referencestring = "No author information. "
            else:
                referencestring = self.authorstring+", "
            referencestring += self.journalstring()
        except:
            referencestring = "Failed to create reference string"
        return referencestring

    def getFromCIF(self, cifblock=None):
        # Get long compound name
        self.compound = cifblock.get('_chemical_name_systematic')
        if type(self.compound) == None:
            self.compound = cifblock.get('_chemical_name_mineral')
            if type(self.compound) == None:
                self.compound = ""
        # Get short compound name
        try:
            self.cpd = cifblock.get('_chemical_formula_structural')
        except:
            try:
                self.cpd = cifblock.get('_chemical_formula_sum')
            except:
                self.cpd = ""
        if type(self.compound) != str:
            self.compound = ""
        if type(self.cpd) != str:
            self.cpd = ""
        # Ty to set up chemical content set
        try:
            tmp = cifblock.get('_chemical_formula_sum').split()
            alloy = False
            for t in tmp:
                e = t.strip(string.digits+string.punctuation)
                n = max(t.strip(string.ascii_letters+string.punctuation),'1')
                try:
                    n = int(n)
                except:
                    try:
                        n = float(n)
                        alloy = True
                    except:
                        raise ValueError()
                if e in self.ChemicalComposition.keys():
                    nold = self.ChemicalComposition[e]
                    self.ChemicalComposition[e] = nold+n
                else:
                    self.ChemicalComposition[e] = n
            if not alloy:
                L = list(self.ChemicalComposition.values())
                divisor = reduce(gcd,L)
                for k,v in self.ChemicalComposition.items():
                    self.ChemicalComposition[k] = v/divisor
        except:
            # If not found, then ignore, this is just to test internal consistency.
            pass
        # Try to identify a source database for the CIF
        for db in self.databasenames:
            # First all the standard ones
            try:
                tmp = cifblock.get('_database_code_'+db)
                if type(tmp) != None:
                    self.databasecode = tmp
                    self.database = self.databasenames[db]
                    self.databasestring = "CIF file exported from "+self.database+\
                                     ".\nDatabase reference code: {}.".format(self.databasecode)
                    break
                else:
                    pass
            except KeyError:
                pass
            try:
                self.databasestring
            except AttributeError:
                self.databasecode = ""
                self.database = ""
                self.databasestring = ""
        # Check if it is a COD file
        if self.databasecode == "":
            try:
                tmp = cifblock.get('_cod_database_code')
                if type(tmp) != None:
                    self.databasecode = tmp
                    self.database = self.databasenames["COD"]
                    self.databasestring = "CIF file exported from "+self.database+\
                                          ".\nDatabase reference code: "+self.databasecode+"."
            except:
                pass
        #
        # Get bibliographic information
        #
        try:
        # Authors
            authorsloop = cifblock.GetLoop('_publ_author_name')
            self.authors = authorsloop.get('_publ_author_name')
            if type(self.authors) == str:
                self.authors = deletenewline(self.authors)
                self.authorstring = self.authors
                self.authors = self.authors.split(";")
            if len(self.authors) == 1:
                self.authorstring = self.authors[0]
            elif len(self.authors) == 2:
                self.authorstring = self.authors[0]+" and "+self.authors[1]
            elif len(self.authors) > 2:
                self.authorstring = self.authors[0]+" et al."
        except KeyError:
            self.authors = []
            self.authorstring = "Failed to get author information"
        # Get rid of newline characters
        self.authorstring = deletenewline(self.authorstring)
        # Title of the paper
        try:
            self.title = cifblock.get('_publ_section_title')
            self.title = deletenewline(self.title,replace=" ")
            self.title = self.title.replace("  "," ")
            self.title = self.title.strip(" ")
        except:
            pass
        # Journal details
        failed = False
        try:
            # Look for citation block.
            references = cifblock.GetLoop('_citation_id')
            # Pick primary reference (or the first in the list, if not found)
            i = 0
            try:
                while references.get('_citation_id')[i] != "primary":
                    i = i + 1
            except IndexError:
                # No primary reference found, using the first one.
                i = 0
            # journal/book title
            if type(references.get('_citation_journal_full')) != None:
                self.journal = references.get('_citation_journal_full')[i]
            else:
                if type(references.get('_citation_journal_abbrev')) != None:
                    self.journal = references.get('_citation_journal_abbrev')[i]
                else:
                    if type(references.get('_citation_book_title')) != None:
                        self.journal = references.get('_citation_book_title')[i]
                    else:
                        self.journal = ""
            # volume
            if type(references.get('_citation_journal_volume')) != None:
                self.volume = references.get('_citation_journal_volume')[i]
            else:
                self.volume = ""
            if type(self.volume) == None:
                self.volume = ""
            # first page
            if type(references.get('_citation_page_first')) != None:
                self.firstpage = references.get('_citation_page_first')[i]
            else:
                self.firstpage = ""
            if type(self.firstpage) == None:
                self.firstpage = ""
            # last page
            if type(references.get('_citation_page_last')) != None:
                self.lastpage = references.get('_citation_page_last')[i]
            else:
                self.lastpage = ""
            if type(self.lastpage) == None:
                self.lastpage = ""
            # year
            if type(references.get('_citation_year')) != None:
                self.year = references.get('_citation_year')[i]
            else:
                self.year = ""
            if type(self.year) == None:
                self.year = ""
        except KeyError:
            try:
                # journal
                self.journal = cifblock.get('_journal_name_full')
                # volume
                self.volume = cifblock.get('_journal_volume')
                # pages
                self.firstpage = cifblock.get('_journal_page_first')
                self.lastpage = cifblock.get('_journal_page_last')
                # year
                self.year = cifblock.get('_journal_year')
            except KeyError:
                failed = True
        if self.journal == None:
            failed = True
            self.journal = ""
        if self.volume == None:
            failed = True
            self.volume = ""
        if self.firstpage == None:
            failed = True
            self.firstpage = ""
        if self.lastpage == None:
            failed = True
            self.lastpage = ""
        if self.year == None:
            failed = True
            self.year = ""
        if not failed:
            # get rid of newline characters
            try:
                self.journal = deletenewline(self.journal)
            except:
                self.journal = "??????"
            try:
                self.volume = deletenewline(self.volume)
            except:
                self.volume = "??"
            try:
                self.firstpage = deletenewline(self.firstpage)
            except:
                self.firstpage = "??"
            try:
                self.lastpage = deletenewline(self.lastpage)
            except:
                self.lastpage = "??"
            try:
                self.year = deletenewline(self.year)
            except:
                self.year = "????"

