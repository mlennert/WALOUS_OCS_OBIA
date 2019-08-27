#!/usr/bin/python
# -*- coding: utf-8 -*-

import os, time, sys, math
import grass.script as gscript
from grass.pygrass.modules.grid.grid import GridModule

# DEBUT DE LA CONFIGURATION

QUIET = True
DEBUG = False
if DEBUG:
    os.environ['GRASS_VERBOSE'] = '3'
# Effacer les fichiers intermédiaires ?
REMOVE = True

RESULTS_DIR = '/projects/walous/FINALRESULTS'

# Sortir une version tif des segments ?
TIFF_OUTPUT_SEGMENTS = True

# Le code inclut la possibilité de créer une deuxième couche de segments
# plus grands. Mais cette approche rallonge fortement le temps de calcul.
WITH_2_SEGMENTATION_LEVELS = False

# Effacer la version vectorielle des segments avec leur stats ?
VECTOR_REMOVE = True

# Sauvegarder la region de travail actuelle et récupérer le nom du mapset
initregion = 'walous_temp_initregion_%i' % os.getpid()
gscript.run_command('g.region',
                    flags='u',
                    save=initregion,
                    overwrite=True)

mapset = gscript.gisenv()['MAPSET']

# TUILES EXISTANTES POUR DETERMINER LES CUTLINES
EXISTING_TILE_MAP='existing_tiles'
EXISTING_CUTLINE_MAP='existing_cutlines'
OUTPUT_STATS_FILE_PREFIX = 'walous_2018_stats_tile_'

# RECUPERER LES ID DES TUILES DES ORTHOS
TUILESCARTE = 'tuilage_2018'
# COUCHE DANS LAQUELLE TROUVER LES ID des tuiles
TUILESCARTE_LAYER = 1

MEMORY=10000
PROCESSES=8
GROUP='walous_tmp_group_%i' % os.getpid()

# DEFINIR LES BANDES DES ORTHOS
# Dans les TIFs des orthos:
# 1 = Rouge
# 2 = Vert
# 3 = Bleu
# 4 = Infrarouge
# Lors de l'importation dans GRASS GIS, chaque bande devient une couche raster
# à part

BANDS = {}
BANDS['red'] = 'orthos2018.1'
BANDS['green'] = 'orthos2018.2'
BANDS['blue'] = 'orthos2018.3'
BANDS['nir'] = 'orthos2018.4'

# Puisque l'ordre des entrées dans un dictionnaire n'est pas garantie dans 
# Python, nous créons un vecteur avec les noms des bandes.
# Garder cet ordre rend le traitement en masse des fichiers plus facile.
bandnames = ['red', 'green', 'blue', 'nir']

# FAUT-IL EXCLURE LE NIR POUR LA SEGMENTATION DES ZONES DE VEGETATION (FOREST ET SIGEC)
# Ceci permets souvent d'éviter des segments trop petits
NO_NIR_FOR_VEGETATION = True

# DEFINITION DES PARAMETRES DE CALCULS DES TEXTURES
# LES TEXTURES SERONT CALCULEES SUR LA "PANCHROMATIQUE", CAD LA COMBINAISON DES RGB
# SI TEXTURE_METHOD = [] ALORS PAS DE TEXTURES CALCULEES
TEXTURE_METHODS = ['idm']
TEXTURE_WINDOWSIZES = [11, 21]
TEXTURE_DISTANCE = 5

# DICTIONNAIRE NECESSAIRE POUR CONNAITRE NOMS DES FICHIERS SORTANT DES CALCULS DE TEXTURE
TEXTURE_METHODS_DIC = {'asm' : 'ASM',
               'contrast' : 'Contr',
               'corr' : 'Corr',
               'var' : 'Var',
               'idm' : 'IDM',
               'sa' : 'SA',
               'sv' : 'SV',
               'se' : 'SE',
               'entr' : 'Entr',
               'dv' : 'DV',
               'de' : 'DE',
               'moc1' : 'MOC-1',
               'moc2' : 'MOC-2'}

# Cartes avec le modèle numérique de hauteur
MNHMAP = 'mnh2018' 

# Cartes de référence pour sélectionner les segments d'entraînement
BUILDINGSMAP = 'sq_batiments'

# Dans le squelette vectorielle créé dans le cadre de WALOUS, les routes
# sont représentées par des polygones
# Les axes de routes dans le PICC permettent un traitement plus rapide et 
# semblent suffisantes pour avoir de bonnes données d'entraînement
#ROADSMAP = 'sq_roads'
ROADSMAP = 'picc_axes_routes_sans_chemins'
ROADS_OVERLAY_OPERATOR = 'crosses'

RAILMAP = 'PICC_ferrov'
RAIL_OVERLAY_OPERATOR = 'crosses'

FIELDSMAP = 'sigec2017_sans_autres'
ARABLESMAP= 'sigec2017_cultures'
#ARABLESMAP = 'crop2016_cm'
CONIFEROUSMAP = 'gembloux_resineux'
DECIDUOUSMAP = 'gembloux_feuillus'
WATERMAP = 'lifewatch_water'
QUARRYMAP = 'IGN_carrieres'

RASTER_STATS = ['mean','stddev','first_quart','perc_90']
RASTER_STATS2 = ['mean','stddev']
AREA_MEASURES = ['area','perimeter','compact_circle','fd','xcoords','ycoords']
AREA_MEASURES2 = ['area','compact_circle','fd']
ISEGMENTSTATSFLAGS='rnc'
ISEGMENTSTATSFLAGS2='rc'

# NOM DE LA COLONNE POUR LES CLASSES DEFINIES POUR L'ENTRAINEMENT
TRAINING_COLUMN = "tr_class"
overlay_TRAINING_COLUMN = "a_" + TRAINING_COLUMN


