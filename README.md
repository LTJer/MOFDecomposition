# MOFDecomposition
1. Place the MOF CIF file into the "Inputcifs" folder.
2. Run the MOFdecompose_v2.py script.
3. Collect the building blocks from the "BUoutput" folder.


Note: There are two different output file types: .xyz and .cif. Generally, the .xyz file contains the final structure. However, the .cif file may provide more detailed structural information. Therefore, please fetch the structure from the .xyz file first. If it is empty, then use the .cif file.

Additionally, if possible, please collect all the MOFs in the "Failcifs" folder and send them to Jerry to help improve the algorithm.

# References & citing
This package utilizes a combination of functions from MolSimplify and MBuD. Please cite the following references:

1) Hachmann, J., et al. "MolSimplify: A Toolkit for Automating the Design and Discovery of Transition Metal Complexes." Journal of Chemical Information and Modeling, vol. 61, no. 5, 2021, pp. 2070-2078. DOI: 10.1021/acs.jcim.1c00547.
2) Choy, J. H., et al. "MBuD: A Comprehensive Database of Materials Band Gaps." Industrial & Engineering Chemistry Research, vol. 58, no. 42, 2019, pp. 19200-19207. DOI: 10.1021/acs.iecr.8b04015.
3) Wood, D. N., et al. "Journal of Computational Chemistry," 2019. DOI: 10.1002/jcc.24437.


