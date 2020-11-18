#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
WALOUS_OCS_OBIA - Copyright (C) <2020> <Service Public de Wallonie (SWP), Belgique,
					          		Institut Scientifique de Service Public (ISSeP), Belgique,
									Université catholique de Louvain (UCLouvain), Belgique,
									Université Libre de Bruxelles (ULB), Belgique>
						 							
	
List of the contributors to the development of WALOUS_OCS_OBIA: see LICENSE file.
Description and complete License: see LICENSE file.
	
This program (WALOUS_OCS_OBIA) is free software: 
you can redistribute it and/or modify it under the terms of the 
GNU General Public License as published by the Free Software 
Foundation, either version 3 of the License, or (at your option) 
any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program (see COPYING file).  If not, 
see <http://www.gnu.org/licenses/>.
"""

import os, sys
import random

RESULTS_PATH = '/projects/walous/FINALRESULTS'
OUT_PATH = '/projects/walous/FINALRESULTS/TRAININGFILES'

STRATA_FILEPATH = '/u/mlennert/WALOUS/STRATAFILES'

SEGMENTATION_RESULTS_FILE_PREFIX = 'walous_2018_stats_tile'

HEADER_FILE='/u/mlennert/WALOUS/SRC/result_header'
HEADER = open(HEADER_FILE, 'r').read().strip().split(',')
HEADER = HEADER[1:129]

MAX_CLASS_SIZE=100000.0

STRATUM = sys.argv[1]

STRATUM_TILE_LIST='%s.csv' % STRATUM
TRAINING_FILE='walous_training_%s.csv' % STRATUM

filepath = os.path.join(STRATA_FILEPATH, STRATUM_TILE_LIST)
tuile_list = open(filepath, 'r').read().splitlines()

filepath = os.path.join(OUT_PATH, TRAINING_FILE)
outfile = open(filepath, 'w')

outfile.write(','.join(HEADER))
outfile.write('\n')

# Afin de ne pas créer des fichiers d'entraînement trop gros, nous prenons un
# échantillon aléatoire de 200000 par classe, si la classe à plus de 200000 segments.
# Pour cela nous devons d'abord compter le nombre de segments par classe.
# [On pourrait éventuellement intégrer ce comptage dans l'identification de ces 
# segments et stocker cette information dans des fichiers annexes.]
classes = {}
for tuile in tuile_list:
    TUILE_FILENAME = "%s_%s.csv" % (SEGMENTATION_RESULTS_FILE_PREFIX, tuile)
    TUILE_FILEPATH = os.path.join(RESULTS_PATH, TUILE_FILENAME)
    if not os.path.isfile(TUILE_FILEPATH):
        continue
    firstline = True
    with open(TUILE_FILEPATH, 'r') as fin:
        for line in fin:
            if firstline:
                firstline = False
                continue
            data = line.rstrip().split(',')
            if len(data) < 129:
                continue
            if data[128] and data[128] != '9':
                if data[128] in classes:
                    classes[data[128]] += 1
                else:
                    classes[data[128]] = 1

classproportions = {}
for myclass in classes:
    classproportions[myclass] = min(1, MAX_CLASS_SIZE/classes[myclass])

for tuile in tuile_list:
    TUILE_FILENAME = "%s_%s.csv" % (SEGMENTATION_RESULTS_FILE_PREFIX, tuile)
    TUILE_FILEPATH = os.path.join(RESULTS_PATH, TUILE_FILENAME)
    if not os.path.isfile(TUILE_FILEPATH):
        continue
    firstline = True
    with open(TUILE_FILEPATH, 'r') as fin:
        for line in fin:
            if firstline:
                firstline = False
                continue
            line = line.strip()
            data = line.split(',')

            if len(data) < 129:
                print "error in file %s, cat %s !" % (TUILE_FILENAME, data[0])
            else: 
                # Les résultats semblent meilleurs en excluant la classe
                # générique "ombres" (9)
                if data[128] and data[128] != '9':
                    # Ici une procédure aléatoire décide si la ligne est
                    # gardée pour l'entraînement
                    if random.random() <= classproportions[data[128]]:
                        line_to_write = data[1:129]
                        outfile.write(','.join(line_to_write))
                        outfile.write('\n')

outfile.close()
