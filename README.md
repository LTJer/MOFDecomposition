# MOFDecomposition
1. Place the MOF CIF file into the "Inputcifs" folder.
2. Run the MOFdecompose_v2.py script.
3. Collect the building blocks from the "BUoutput" folder.


Note: There are two different output file types: .xyz and .cif. Generally, the .xyz file contains the final structure. However, the .cif file may provide more detailed structural information. Therefore, please fetch the structure from the .xyz file first. If it is empty, then use the .cif file.

Additionally, if possible, please collect all the MOFs in the "Failcifs" folder and send them to Jerry to help improve the algorithm.

# References & citing
This package utilizes functions from MolSimplify and mBUD. Please cite the following references:

1) Halder, Prosun, Prerna, and Jayant K. Singh. "Building unit extractor for metal-organic frameworks." Journal of Chemical Information and Modeling 61.12 (2021): 5827-5840.
2) Ioannidis, Efthymios I., Terry ZH Gani, and Heather J. Kulik. "molSimplify: A toolkit for automating discovery in inorganic chemistry." (2016): 2106-2117.
3) Nandy, Aditya, et al. "Strategies and software for machine learning accelerated discovery in transition metal chemistry." Industrial & Engineering Chemistry Research 57.42 (2018): 13973-13986.


