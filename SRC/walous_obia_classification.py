#!/usr/bin/python
# -*- coding: utf-8 -*-

import os, time, sys
import grass.script as gscript

TEST = False

# DEBUT DE LA CONFIGURATION

QUIET = True
# Effacer les fichiers intermédiaires ?
REMOVE = True

DATA_DIR = '/projects/walous/FINALRESULTS/'
RESULTS_DIR = os.path.join(DATA_DIR, 'CLASSIFICATION/SPECIAL_CHECK')
MODEL_DIR = os.path.join(DATA_DIR, 'MODELS')

PROCESSES=8

CLASSIFIER = 'rf'
TRAINING_COLUMN='tr_class'

SEGMENT_RASTER_PREFIX='segs_tile'
CLASSIFICATION_RASTER_PREFIX='classification_tile'
SEGMENT_STATS_PREFIX='walous_2018_stats_tile'
CLASSIFICATION_CSV_OUTPUT='walous_2018_classification_tile'

TUILE = int(sys.argv[1])

STRATUM = gscript.read_command('v.db.select',
                               map_='tuilage_2018',
                               column='stratum',
                               where='cat = %i' % TUILE,
                               flags='c',
                               quiet=True).rstrip()

MODEL_FILE_NAME = 'walous_training_%s_model.rds' % STRATUM
MODEL_FILE_PATH = os.path.join(MODEL_DIR, MODEL_FILE_NAME)

segment_raster_file = "%s_%i.tif" % (SEGMENT_RASTER_PREFIX, TUILE)
classification_raster_file = "%s_%i.tif" % (CLASSIFICATION_RASTER_PREFIX, TUILE)
    
segment_stats_file = "%s_%i.csv" % (SEGMENT_STATS_PREFIX, TUILE)
classification_csv_file = "%s_%i.csv" % (CLASSIFICATION_CSV_OUTPUT, TUILE)

# Necessary because of error in the variable names during stats calculation
# Error now corrected so 'NEWCSV' won't be necessary in the future
segment_stats_input = os.path.join(DATA_DIR, 'NEWCSV', segment_stats_file)
#segment_stats_input = os.path.join(DATA_DIR, segment_stats_file)
segment_raster_input = os.path.join(DATA_DIR, segment_raster_file)
classification_raster_output = os.path.join(RESULTS_DIR, classification_raster_file)
classification_csv_output = os.path.join(RESULTS_DIR, classification_csv_file)
classification_raster_grass = "%s_%i" % (CLASSIFICATION_RASTER_PREFIX, TUILE)

gscript.message("Tile %i" % TUILE)
start_time = time.time()

if os.path.isfile(classification_raster_output) and os.path.isfile(classification_csv_output):
    gscript.message("Nothing to do")
    exec_time = time.time() - start_time
    gscript.verbose("Finished with tile %i in %s seconds." % (TUILE, exec_time))
    sys.exit()

# Créer lien vers le fichier raster avec les segments
gscript.run_command('r.external',
                    input_=segment_raster_input,
                    output='walous_temp_segment_raster',
                    overwrite=True,
                    quiet=QUIET)

gscript.run_command('g.region',
                    raster='walous_temp_segment_raster',
                    quiet=QUIET)

print segment_stats_input
gscript.run_command('v.class.mlR',
                    flags='p',
                    segments_file=segment_stats_input,
                    separator='comma',
                    classifier=CLASSIFIER,
                    train_class_column=TRAINING_COLUMN,
                    input_model_file=MODEL_FILE_PATH,
                    raster_segment_map='walous_temp_segment_raster',
                    classified_map=classification_raster_grass,
                    classification_results=classification_csv_output,
                    processes=PROCESSES,
                    overwrite=True,
                    quiet=QUIET)

gscript.run_command('r.out.gdal',
                    input_="%s_%s" % (classification_raster_grass, CLASSIFIER),
                    output=classification_raster_output,
                    flags='cm',
                    createopt='COMPRESS=LZW,TILED=YES',
                    overwrite=True,
                    quiet=QUIET)

exec_time = time.time() - start_time
gscript.verbose("Finished with tile %i in %s seconds." % (TUILE, exec_time))
