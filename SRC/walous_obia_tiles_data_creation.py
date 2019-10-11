#!/usr/bin/python
# -*- coding: utf-8 -*-

import os, time, sys, math
import grass.script as gscript
from grass.pygrass.modules.grid.grid import GridModule

# Quelques fonctions supplémentaires se trouvent dans un fichier à part
from walous_obia_functions import fill_band, tile_size, calculate_panvis

# L'ensemble des paramètres à configurer se trouve dans le fichier
# de configuration
from walous_obia_config import *

TUILE = int(sys.argv[1])

gscript.message("Tile %i" % TUILE)
total_start_time = time.time()

# Si le tiff avec les segments existe déjà, il suffit de l'importer, au lieu de le recréer
tiff_outputmap = 'segs_tile_%i.tif' % TUILE
testoutput=os.path.join(RESULTS_DIR, tiff_outputmap)

if os.path.isfile(testoutput):
    output_file = OUTPUT_STATS_FILE_PREFIX + str(TUILE) + '.csv'
    testoutputfile=os.path.join(RESULTS_DIR, output_file)
    if os.path.isfile(testoutputfile):
        gscript.message("Nothing to do")
        sys.exit()

    gscript.message("Using existing segments file")
    segsmap='segs_tile%i' % TUILE

    gscript.run_command('r.in.gdal',
                       input_=testoutput,
                       output=segsmap,
                       quiet=True)

    gscript.run_command('g.region',
                        raster=segsmap,
                        quiet=True)

    # Si les orthophotos contiennent des pixels NULL, cela peut
    # perturber l'analyse. Nous appliquons donc un simple filtre de
    # moyenne pondérée par la distance avec une fenêtre 3x3 pour remplir
    # ces pixels avec une valeur estimée.
    # S'il n'y a pas de pixels NULLS, rien n'est modifié.
    tilemask = gscript.tempname(20)
    mapcalc_expression = "%s = if(%s)" % (tilemask, segsmap)
    gscript.run_command('r.mapcalc',
                        expression=mapcalc_expression,
                        quiet=QUIET)

    for band, bandmap in BANDS.items():
        null_test = gscript.read_command('r.stats',
                                         flags='N',
                                         input_=[tilemask,bandmap],
                                         quiet=QUIET).splitlines()

        # '1 *' signifie qu'il y a bien une valeur dans le mask de la tuile
        # mais pas de valeur (donc pixel à valeur nulle" dans l'ortho).
        # Pour avoir les mêmes noms de colonnes, il vaut mieux que les rasters
        # ont tous les mêmes noms, du l'opération du 'else:' qui permet
        # de créer une nouvelle couche virtuelle, tout à fait équivalent à
        # l'original, mais avec un autre nom.
        if '1 *' in null_test:
            BANDS[band] = fill_band(bandmap, tilemask)
        else:
            reclass_rule = '* = *'
            filled_band = "%s_filled" % bandmap
            gscript.write_command('r.reclass',
                                 input_=bandmap,
                                 output=filled_band,
                                 rules='-',
                                 stdin=reclass_rule,
                                 quiet=QUIET)
            BANDS[band] = filled_band


    if REMOVE:
        gscript.run_command('g.remove',
                            type='raster',
                            name=tilemask,
                            flags='f',
                            quiet=QUIET)

    # Calculer taille des tuiles pour parallélisation des calculs de raster
    x_tile_size, y_tile_size = tile_size(PROCESSES)

    start_time = time.time()
    gscript.verbose("Creating panchromatic image.")
    # Calculer l'image panchromatique, utilisée pour les cutlines et les textures
    panvis_map = calculate_panvis(BANDS, x_tile_size, y_tile_size, PROCESSES, TUILE)

    total_time = time.time() - start_time
    gscript.verbose("Panchromatic in %s." % str(total_time))


else:

    soustuiles='subtiles%i' % TUILE

    temp_tile = 'walous_temptile_%i' % os.getpid()
    temp_tiles_map1 = 'walous_temptiles1_%i' % os.getpid()
    temp_tiles_map1_clumped = 'walous_temptiles1_clumped_%i' % os.getpid()
    temp_tiles_map2 = 'walous_temptiles2_%i' % os.getpid()
    temp_tiles_map3 = 'walous_temptiles3_%i' % os.getpid()

    # Récupérer le contour de la tuile et ajuster la région de calcul
    gscript.run_command('v.extract',
                        input_=TUILESCARTE,
                        layer=TUILESCARTE_LAYER,
                        cat=TUILE,
                        out=temp_tile,
                        flags='t',
                        quiet=QUIET,
                        overwrite=True)

    gscript.run_command('g.region',
                        vector=temp_tile,
                        align=BANDS['red'],
                        res=0.25,
                        quiet=QUIET)

    gscript.run_command('v.to.rast',
                        input_=EXISTING_TILE_MAP,
                        use='cat',
                        output=EXISTING_TILE_MAP,
                        memory=MEMORY,
                        overwrite=True,
                        quiet=QUIET)
                        

    # Si les orthophotos contiennent des pixels NULL, cela peut
    # perturber l'analyse. Nous appliquons donc un simple filtre de
    # moyenne pondérée par la distance avec une fenêtre 3x3 pour remplir
    # ces pixels avec une valeur estimée.
    # S'il n'y a pas de pixels NULLS, rien n'est modifié.
    tilemask = gscript.tempname(20)
    gscript.run_command('v.to.rast',
                        input_=temp_tile,
                        use='val',
                        output=tilemask,
                        memory=MEMORY,
                        quiet=QUIET)

    for band, bandmap in BANDS.items():
        null_test = gscript.read_command('r.stats',
                                         flags='N',
                                         input_=[tilemask,bandmap],
                                         quiet=QUIET).splitlines()

        # '1 *' signifie qu'il y a bien une valeur dans le mask de la tuile
        # mais pas de valeur (donc pixel à valeur nulle" dans l'ortho).
        # Pour avoir les mêmes noms de colonnes, il vaut mieux que les rasters
        # ont tous les mêmes noms, du l'opération du 'else:' qui permet
        # de créer une nouvelle couche virtuelle, tout à fait équivalent à
        # l'original, mais avec un autre nom.
        if '1 *' in null_test:
            BANDS[band] = fill_band(bandmap, tilemask)
        else:
            reclass_rule = '* = *'
            filled_band = "%s_filled" % bandmap
            gscript.write_command('r.reclass',
                                 input_=bandmap,
                                 output=filled_band,
                                 rules='-',
                                 stdin=reclass_rule,
                                 quiet=QUIET)
            BANDS[band] = filled_band

    if REMOVE:
        gscript.run_command('g.remove',
                            type='raster',
                            name=tilemask,
                            flags='f',
                            quiet=QUIET)

    # Calculer taille des tuiles pour parallélisation des calculs de raster
    x_tile_size, y_tile_size = tile_size(PROCESSES)

    start_time = time.time()
    gscript.verbose("Creating panchromatic image.")
    # Calcule l'image panchromatique, utilisée pour les cutlines et les textures
    panvis_map = calculate_panvis(BANDS, x_tile_size, y_tile_size, PROCESSES, TUILE)

    total_time = time.time() - start_time
    gscript.verbose("Panchromatic in %s." % str(total_time))

    start_time = time.time()
    gscript.verbose("Creating cutlines.")
    # Créer les cutlines pour les sous-tuiles
    gscript.run_command('i.cutlines',
                        input_=panvis_map,
                        number_lines=15,
                        processes=PROCESSES,
                        memory=MEMORY,
                        output=temp_tiles_map1,
                        existing_cutlines=EXISTING_CUTLINE_MAP,
                        tile_width=1000,
                        tile_height=1000,
                        overlap=1,
                        edge_detection='zc',
                        min_tile_size=15625,
                        no_edge_friction=20,
                        lane_border_multiplier=500,
                        overwrite=True,
                        quiet=QUIET)

    gscript.run_command('v.to.rast',
                        input_=temp_tiles_map1,
                        output=temp_tiles_map1,
                        use='cat',
                        memory=MEMORY,
                        overwrite=True,
                        quiet=QUIET)

    # Clumping the output to restart cat values at 1 and avoid
    # too large values in the next step
    gscript.run_command('r.clump',
                        input_=temp_tiles_map1,
                        output=temp_tiles_map1_clumped,
                        overwrite=True,
                        quiet=QUIET)

    gscript.verbose("Combining existing tiles with cutline tiles.")

    # Add 10e6 to cat values to differentiate from existing tile cat values
    mapcalc_expression = "%s = %s + 1000000" % (temp_tiles_map2, temp_tiles_map1_clumped)

    gscript.run_command('r.mapcalc.tiled',
                        expression=mapcalc_expression,
                        tile_width=x_tile_size,
                        tile_height=y_tile_size,
                        overlap=0,
                        processes=PROCESSES,
                        mapset_prefix='rmapcalc_%i' % TUILE,
                        quiet=QUIET)

    gscript.run_command('r.mask',
                        vector=temp_tile,
                        overwrite=True,
                        quiet=QUIET)

    gscript.run_command('r.patch',
                        input_=[EXISTING_TILE_MAP, temp_tiles_map2],
                        output=temp_tiles_map3,
                        overwrite=True,
                        quiet=QUIET)

    # Avoid very small tiles (here < 500m2)
    gscript.run_command('r.reclass.area',
                        input_=temp_tiles_map3,
                        value=0.05,
                        mode='lesser',
                        method='rmarea',
                        output=soustuiles,
                        overwrite=True,
                        quiet=QUIET)

    if REMOVE:
        gscript.run_command('g.remove',
                            type='raster',
                            name=[temp_tiles_map1,temp_tiles_map1_clumped,temp_tiles_map2,temp_tiles_map3],
                            flags='f',
                            quiet=QUIET)

        gscript.run_command('g.remove',
                            type='vect',
                            name=[temp_tiles_map1,temp_tile],
                            flags='f',
                            quiet=QUIET)

    gscript.run_command('r.mask',
                        flags='r',
                        quiet=QUIET)

    total_time = time.time() - start_time
    gscript.verbose("Subtiles in %s." % str(total_time))

    temp_slic_map = 'walous_tempslicmap_%i' % os.getpid()

    segmentation_start_time = time.time()
    # Work on each individual cutline tile
    for cat in gscript.read_command('r.stats',
                                    input_=soustuiles,
                                    flags='n',
                                    quiet=QUIET).splitlines():

        gscript.verbose("Working on subtile %s in TILE %i." % (cat, TUILE))

        gscript.run_command('r.mask',
                            raster=soustuiles,
                            maskcats=cat,
                            overwrite=True,
                            quiet=QUIET)

        temp_region = 'region_tile%i_cat%s' % (TUILE, cat)
        gscript.run_command('g.region',
                            zoom='MASK',
                            res=0.25,
                            save=temp_region,
                            overwrite=True,
                            quiet=QUIET)


        start_threshold = 0.015
        stop_threshold = 0.030
        step = 0.002
        minsize = 32 # 2m2
        # Deuxième niveau de segmentation pour avoir des objets plus grands de context
        start_threshold2 = 0.090
        stop_threshold2 = 0.105
        step2 = 0.002
        minsize2 = 320 # 20m2
        f_function_alpha = 1
        superpixels_step = 2
        superpixels_compacity = 0.7

        # cat < 1000000 means that the tile comes from the 
        # existing tiles which represent agricultural areas or forests.
        # We can, therefore, create larger segments.
        # We also delete NIR from the bands used for segmentations in order to
        # obtain bigger segments

        import copy
        TMPBANDS = copy.deepcopy(BANDS)

        if int(cat) < 1000000:
            start_threshold = 0.025
            stop_threshold = 0.040
            minsize = 64 #4m2
            # Deuxième niveau de segmentation pour avoir des objets plus grands de context
            start_threshold2 = 0.100
            stop_threshold2 = 0.115
            minsize2 = 640 # 40 m2
            f_function_alpha = 0.7
            superpixels_step = 20
            superpixels_compacity = 1
            if NO_NIR_FOR_VEGETATION:
                del TMPBANDS['nir']

        gscript.run_command('i.group',
                            group=GROUP,
                            input_=[x for x in TMPBANDS.values()],
                            quiet=QUIET)

        gscript.verbose("SLIC.")

        superpixels_found = False

        # Essayer de créer des superpixels. Si cela ne fonctionne pas
        # (généralement parce qu'on utilise un 'step' trop grand)
        # diminuer le step de 1 et réessayer.
        while not superpixels_found:
            try:
                os.environ['GRASS_VERBOSE'] = '-1'
                gscript.run_command('i.superpixels.slic',
                                    input=GROUP,
                                    step=superpixels_step,
                                    compact=superpixels_compacity,
                                    output=temp_slic_map,
                                    perturb=5,
                                    memory=MEMORY,
                                    overwrite=True,
                                    quiet=QUIET)
                del os.environ['GRASS_VERBOSE']
                if DEBUG:
                    os.environ['GRASS_VERBOSE'] = '3'

                superpixels_found = True

            except:
                superpixels_step = superpixels_step - 1

        gscript.verbose("USPO.")
        start_time = time.time()
        # Run USPO on the cutline tile
        gscript.run_command('i.segment.uspo',
                            group=GROUP,
                            seeds=temp_slic_map,
                            segment_map='segs',
                            regions=temp_region,
                            tstart=start_threshold,
                            tstop=stop_threshold,
                            tstep=step,
                            minsizes=minsize,
                            optimization_function='f',
                            f_function_alpha=f_function_alpha,
                            memory=MEMORY,
                            processes=PROCESSES,
                            overwrite=True,
                            quiet=QUIET)
        total_time = time.time() - start_time
        gscript.verbose("USPO in %s." % str(total_time))

        if WITH_2_SEGMENTATION_LEVELS:
            gscript.verbose("USPO2.")
            start_time = time.time()
            segment_output1 = 'segs_%s_rank1' % temp_region
            gscript.run_command('i.segment.uspo',
                                group=GROUP,
                                seeds=segment_output1,
                                segment_map='segs2',
                                regions=temp_region,
                                tstart=start_threshold2,
                                tstop=stop_threshold2,
                                tstep=step2,
                                minsizes=minsize2,
                                optimization_function='f',
                                f_function_alpha=f_function_alpha,
                                memory=MEMORY,
                                processes=PROCESSES,
                                overwrite=True,
                                quiet=QUIET)
            total_time = time.time() - start_time
            gscript.verbose("USPO2 in %s." % str(total_time))

        '''except:
            # Si toute la sous-tuile devient un seul superpixel, alors on 
            # déclare l'ensemble de la sous-tuile comme un seul segment.
            one_segment_map = "segs_region_tile%i_%s" % (TUILE, cat)
            mapcalc_expression = "%s = -1" % one_segment_map
            gscript.run_command('r.mapcalc',
                                expression=mapcalc_expression,
                                overwrite=True,
                                quiet=QUIET)'''
                                
        gscript.run_command('r.mask',
                            flags='r',
                            quiet=QUIET)

        if REMOVE:
            gscript.run_command('g.remove',
                                type_='raster',
                                name=temp_slic_map,
                                flags='f',
                                quiet=QUIET)

            gscript.run_command('g.remove',
                                type_='region',
                                name=temp_region,
                                flags='f',
                                quiet=QUIET)

        gscript.run_command('g.region',
                            raster=soustuiles,
                            res=0.25,
                            quiet=QUIET)

    all_maps = gscript.list_strings(type='raster',
                                    pattern='segs_region_tile%i_*' % TUILE)

    if WITH_2_SEGMENTATION_LEVELS:
        all_maps2 = gscript.list_strings(type='raster',
                                         pattern='segs2_region_tile%i_*' % TUILE)

    gscript.verbose("Patching.")
    try:
        if len(all_maps) > 1:
            temp_patched_map = 'walous_temppatchedmap_%i' % os.getpid()
            gscript.run_command('r.patch',
                                input_=all_maps,
                                output=temp_patched_map,
                                overwrite=True,
                                quiet=QUIET)
            # As we've patched different tiles with overlapping category numbers
            # for objects, we run r.clump to get unique cat values per object
            gscript.run_command('r.clump',
                                input_=temp_patched_map,
                                output='segs_tile%i' % TUILE,
                                overwrite=True,
                                quiet=QUIET)
                                
            if WITH_2_SEGMENTATION_LEVELS:
                # Now do the same for the larger segments
                gscript.run_command('r.patch',
                                    input_=all_maps2,
                                    output=temp_patched_map,
                                    overwrite=True,
                                    quiet=QUIET)
                gscript.run_command('r.clump',
                                    input_=temp_patched_map,
                                    output='segs2_tile%i' % TUILE,
                                    overwrite=True,
                                    quiet=QUIET)
                                
        else:
            gscript.run_command('g.rename',
                                raster=[all_maps[0],'segs_tile%i' % TUILE],
                                overwrite=True,
                                quiet=QUIET)

            if WITH_2_SEGMENTATION_LEVELS:
                gscript.run_command('g.rename',
                                    raster=[all_maps2[0],'segs2_tile%i' % TUILE],
                                    overwrite=True,
                                    quiet=QUIET)

    except:
        gscript.message("Couldn't patch raster tiles for tile number %i." % TUILE)


    # Clean up
    if REMOVE:
        gscript.run_command('g.remove',
                            type='raster',
                            name=soustuiles,
                            flags='f',
                            quiet=QUIET)

        if len(all_maps) > 1:
            gscript.run_command('g.remove',
                                type_='raster',
                                name=all_maps,
                                flags='f',
                                quiet=QUIET)

    gscript.run_command('g.remove',
                        type_='group',
                        name=GROUP,
                        flags='f',
                        quiet=QUIET)

    gscript.verbose("Exporting segment tiffs.")
    if TIFF_OUTPUT_SEGMENTS:
        tiff_outputmap = 'segs_tile_%i.tif' % TUILE
        gscript.run_command('r.out.gdal',
                            input_='segs_tile%i' % TUILE,
                            output=os.path.join(RESULTS_DIR, tiff_outputmap),
                            flags='cm',
                            createopt='COMPRESS=LZW,TILED=YES',
                            quiet=True,
                            overwrite=True)
                    
        if WITH_2_SEGMENTATION_LEVELS:
            tiff_outputmap = 'segs2_tile_%i.tif' % TUILE
            gscript.run_command('r.out.gdal',
                                input_='segs2_tile%i' % TUILE,
                                output=os.path.join(RESULTS_DIR, tiff_outputmap),
                                flags='cm',
                                createopt='COMPRESS=LZW,TILED=YES',
                                quiet=True,
                                overwrite=True)
                        
    total_time = time.time() - segmentation_start_time
    gscript.verbose("Segmentation in %s." % str(total_time))

# FIN SEGMENTATION

# DEBUT EXTRACTION ZONES ENTRAINEMENT

# Ajouter quelques pseudo-bandes (mnh, texture, ndvi, ndwi)

RASTERS = []
RASTERS.append(MNHMAP)

# Créer un polygone représentant la région de travail (bounding box) 
# de la tuile
region_vector = 'walous_temp_region_%i' % os.getpid()
gscript.run_command('v.in.region',
                    output=region_vector,
                    type='area',
                    overwrite=True,
                    quiet=QUIET)


# Calculer taille des tuiles pour parallélisation des calculs de raster
x_tile_size, y_tile_size = tile_size(PROCESSES)

gscript.verbose("Calculating texture.")
start_time = time.time()
# CALCULER DES TEXTURES SI CONFIGUREES
if TEXTURE_METHODS:
    # Create texture maps on pseudo-panchro channel and add to group
    for SIZE in TEXTURE_WINDOWSIZES:
        texture_temp_map_prefix = 'walous_temptexturemap_%i' % SIZE
        for TEXTURE_METHOD in TEXTURE_METHODS:
            gscript.run_command('r.texture.tiled',
                                input_=panvis_map,
                                output=texture_temp_map_prefix,
                                method=TEXTURE_METHOD,
                                size=SIZE,
                                distance=TEXTURE_DISTANCE,
                                processes=PROCESSES,
                                mapset_prefix='rtext_%i' % TUILE,
                                overwrite=True,
                                quiet=QUIET)

            method_file_suffix = TEXTURE_METHODS_DIC[TEXTURE_METHOD]
            mapname = texture_temp_map_prefix + '_' + method_file_suffix
            RASTERS.append(mapname)

total_time = time.time() - start_time
gscript.verbose("Texture in %s." % str(total_time))

if REMOVE:
    gscript.run_command('g.remove',
                        type_='raster',
                        name=panvis_map,
                        flags='f',
                        quiet=QUIET)

# CALCULER NDVI POUR LA TUILE
ndvi_formule = "eval(ndvi = float(%s - %s) / float(%s + %s))\n" % (BANDS['nir'], BANDS['red'], BANDS['nir'], BANDS['red'])
ndvimap = 'walous_tempmap_ndvi'
mapcalc_expression = ndvi_formule + "%s = if(isnull(ndvi), 0, ndvi)" % ndvimap

gscript.run_command('r.mapcalc.tiled',
                    expression=mapcalc_expression,
                    output=ndvimap,
                    tile_width=x_tile_size,
                    tile_height=y_tile_size,
                    overlap=0,
                    processes=PROCESSES,
                    mapset_prefix='rmapcalc_%i' % TUILE,
                    quiet=QUIET)

RASTERS.append(ndvimap)

# CALCULER NDWI POUR LA TUILE
ndwi_formule = "eval(ndwi = float(%s - %s) / float(%s + %s))\n" % (BANDS['green'], BANDS['nir'], BANDS['green'], BANDS['nir'])
ndwimap = 'walous_tempmap_ndwi'
mapcalc_expression = ndwi_formule + "%s = if(isnull(ndwi), 0, ndwi)" % ndwimap

gscript.run_command('r.mapcalc.tiled',
                    expression=mapcalc_expression,
                    output=ndwimap,
                    tile_width=x_tile_size,
                    tile_height=y_tile_size,
                    overlap=0,
                    processes=PROCESSES,
                    mapset_prefix='rmapcalc_%i' % TUILE,
                    quiet=QUIET)

RASTERS.append(ndwimap)


gscript.verbose("i.segment.stats 1.")
start_time = time.time()
# Calculer statistiques par ségment et sortir sous forme vectorielle
segs_tile_stats_map = 'segs_tile%i_stats' % TUILE
gscript.run_command('i.segment.stats',
                    flags=ISEGMENTSTATSFLAGS,
                    map_='segs_tile%i' % TUILE,
                    rasters=([BANDS[x] for x in bandnames]+RASTERS),
                    raster_statistics=RASTER_STATS,
                    area_measures=AREA_MEASURES,
                    vectormap=segs_tile_stats_map,
                    processes=PROCESSES,
                    overwrite=True,
                    quiet=QUIET)
total_time = time.time() - start_time
gscript.verbose("i.segment.stats 1 in %s." % str(total_time))

if WITH_2_SEGMENTATION_LEVELS:
    gscript.verbose("i.segment.stats 2.")
    start_time = time.time()
    segs2_tile_stats_map = 'segs2_tile%i_stats' % TUILE
    gscript.run_command('i.segment.stats',
                        flags=ISEGMENTSTATSFLAGS2,
                        map_='segs2_tile%i' % TUILE,
                        rasters=RASTERS,
                        raster_statistics=RASTER_STATS2,
                        area_measures=AREA_MEASURES2,
                        vectormap=segs2_tile_stats_map,
                        processes=PROCESSES,
                        overwrite=True,
                        quiet=QUIET)
    total_time = time.time() - start_time
    gscript.verbose("i.segment.stats 2 in %s." % str(total_time))

    gscript.run_command('v.db.addcolumn',
                    map_=segs_tile_stats_map,
                    col="cat2 int",
                    quiet=QUIET)

    gscript.verbose("v.distance segs to segs2.")
    start_time = time.time()
    gscript.run_command('v.distance',
                        from_=segs_tile_stats_map,
                        to_=segs2_tile_stats_map,
                        upload='cat',
                        column='cat2',
                        quiet=QUIET)
    total_time = time.time() - start_time
    gscript.verbose("v.distance in %s." % str(total_time))

    gscript.verbose("v.db.join2")
    gscript.run_command('v.db.join2',
                        map_=segs_tile_stats_map,
                        column='cat2',
                        other_table=segs2_tile_stats_map,
                        other_column='cat',
                        column_prefix='segs2_',
                        quiet=QUIET)

if REMOVE:
    gscript.run_command('g.remove',
                        type_='raster',
                        name=RASTERS,
                        flags='f',
                        quiet=QUIET)
    if WITH_2_SEGMENTATION_LEVELS:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=segs2_tile_stats_map,
                            flags='f',
                            quiet=QUIET)

# Puisque les sommes des valuers des orthos et du MNH peuvent être trop élevées pour certains programmes
# il faut les réduire. On divise donc la valeur par 10e6
for column in gscript.read_command('v.info',
                                   flags='c',
                                   map_=segs_tile_stats_map,
                                   quiet=QUIET).splitlines():
    cname = column.split('|')[1]
    if 'sum' in cname:
        gscript.run_command('v.db.update',
                            map_=segs_tile_stats_map,
                            column=cname,
                            value='%s/1000000.0' % cname,
                            quiet=QUIET)

# AJOUTER COLONNE QUI CONTIENDRA L'ETIQUETTE DE CLASSE POUR ENTRAINEMENT
gscript.run_command('v.db.addcolumn',
                    map_=segs_tile_stats_map,
                    col="%s int" % TRAINING_COLUMN)

ndvi_mean = '%s_mean' % ndvimap
ndvi_stddev = '%s_stddev' % ndvimap
ndvi_perc90 = '%s_perc_90' % ndvimap
ndwi_mean = '%s_mean' % ndwimap
nir_mean = '%s_mean' % BANDS['nir'].split('@')[0].replace('.', '_')
mnh_mean = '%s_mean' % MNHMAP
overlay_ndvi_mean = "a_" + ndvi_mean
overlay_ndvi_stddev = "a_" + ndvi_stddev
overlay_ndwi_mean = "a_" + ndwi_mean
overlay_mnh_mean = "a_" + mnh_mean
overlay_nir_mean = "a_" + nir_mean



gscript.verbose("Segments d'entrainement.")
# IDENTIFIER DIFFERENTES SEGMENTS D'ENTRAINEMENT CLASSE PAR CLASSE

# BATIMENTS
batiment_start_time = time.time()
gscript.verbose("Bâtiments.")

# Overlay is faster if we use only buildings overlapping the current region
tilebuildingsmap = 'walous_temp_batiment_tile_%i' % os.getpid()

start_time = time.time()
gscript.run_command('v.clip',
                    input_=BUILDINGSMAP,
                    output=tilebuildingsmap,
                    flags='r',
                    overwrite=True,
                    quiet=QUIET)

total_time = time.time() - start_time
gscript.verbose("Clip en %s." % str(total_time))

topoinfo = gscript.vector_info_topo(tilebuildingsmap)
if topoinfo['areas'] > 0:

    # Sélectionner segments dont plus de 95% de la surface tombent dans les
    # bâtiments rétrécis 
    # a_area (from r.object.geometry) is calculated in pixels so we have to 
    # adjust by pixel size
    batiments_overlay_map = 'tile_%i_and_batiments' % TUILE
    
    start_time = time.time()
    gscript.run_command('v.overlay',
                        ain=segs_tile_stats_map,
                        bin_=tilebuildingsmap,
                        out=batiments_overlay_map,
                        op='and',
                        overwrite=True,
                        quiet=QUIET)

    if REMOVE:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=tilebuildingsmap,
                            flags='f',
                            quiet=QUIET)

    total_time = time.time() - start_time
    gscript.verbose("Overlay en %s." % str(total_time))

    # Test whether there are any areas in the results, if not go on to next
    # class
    topoinfo = gscript.vector_info_topo(batiments_overlay_map)
    if topoinfo['areas'] > 0:

        # IDENTIFIER CRITERES POUR OMBRES
        first = True
        for raster in BANDS.values():
            raster = raster.split('@')[0]
            raster = raster.replace('.', '_')

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=batiments_overlay_map,
                                                 column="a_%s_mean" % raster,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            if first:
                overlay_shadowcondition = "(a_%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)
                first = False
            else:
                overlay_shadowcondition += " AND a_%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)

        overlay_shadowcondition += ')'

        start_time = time.time()
        gscript.run_command('v.db.addcolumn',
                            map_=batiments_overlay_map,
                            column='newarea double precision',
                            quiet=QUIET)

        gscript.run_command('v.to.db',
                            map_=batiments_overlay_map,
                            option='area',
                            column='newarea',
                            quiet=QUIET)

        total_time = time.time() - start_time
        gscript.verbose("Calcul surface en %s." % str(total_time))

        start_time = time.time()
        condition = "%s is NULL" % overlay_TRAINING_COLUMN
        condition += " AND newarea/(a_area*0.25*0.25)>0.95"
        condition += " AND %s > 300" % overlay_mnh_mean
        condition += " AND %s" % overlay_shadowcondition

        selcats = gscript.read_command('v.db.select',
                                       map_=batiments_overlay_map,
                                       column='a_cat',
                                       where=condition,
                                       flags='c',
                                       quiet=QUIET).splitlines()

        if len(selcats) > 0:
            sqltempfile = gscript.tempfile()
            with open(sqltempfile, 'w') as fout:
                for cat in selcats:
                    fout.write("UPDATE %s SET %s = 912 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

            gscript.run_command('db.execute',
                                input_=sqltempfile,
                                quiet=QUIET)

            gscript.try_remove(sqltempfile)
            
        total_time = time.time() - start_time
        gscript.verbose("Sélection ombres en %s." % str(total_time))

        start_time = time.time()
        univar_stats = gscript.parse_command('v.db.univar',
                                             map_=batiments_overlay_map,
                                             column=overlay_ndvi_mean,
                                             where="NOT %s" % overlay_shadowcondition,
                                             flags='g',
                                             quiet=QUIET)
        average_mean = univar_stats['mean']
        average_stddev = univar_stats['stddev']

        univar_stats = gscript.parse_command('v.db.univar',
                                             map_=batiments_overlay_map,
                                             column=overlay_ndvi_stddev,
                                             where="NOT %s" % overlay_shadowcondition,
                                             flags='g',
                                             quiet=QUIET)
        stddev_mean = univar_stats['mean']
        stddev_stddev = univar_stats['stddev']

        total_time = time.time() - start_time
        gscript.verbose("Calculs univar en %s." % str(total_time))


        start_time = time.time()
        condition = "%s is NULL" % overlay_TRAINING_COLUMN
        condition += " AND newarea/(a_area*0.25*0.25)>0.95"
        condition += " AND NOT %s" % overlay_shadowcondition
        condition += " AND %s > (%s - %s)" % (overlay_ndvi_mean, average_mean,
                average_stddev)
        condition += " AND %s < (%s + %s)" % (overlay_ndvi_mean, average_mean,
                average_stddev)
        condition += " AND %s < %s" % (overlay_ndvi_stddev, stddev_mean)
        condition += " AND %s > 300" % overlay_mnh_mean

        selcats = gscript.read_command('v.db.select',
                                       map_=batiments_overlay_map,
                                       column='a_cat',
                                       where=condition,
                                       flags='c',
                                       quiet=QUIET).splitlines()
        if len(selcats) > 0:
            sqltempfile = gscript.tempfile()
            with open(sqltempfile, 'w') as fout:
                for cat in selcats:
                    fout.write("UPDATE %s SET %s = 12 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

            gscript.run_command('db.execute',
                                input_=sqltempfile,
                                quiet=QUIET)

            gscript.try_remove(sqltempfile)

        total_time = time.time() - start_time
        gscript.verbose("Sélection sans ombres en %s." % str(total_time))


    if REMOVE:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=batiments_overlay_map,
                            flags='f',
                            quiet=QUIET)

total_time = time.time() - batiment_start_time
gscript.verbose("Bâtiments en %s." % str(total_time))

# SOL IMPERMEABILISE / ROUTES

start_time = time.time()
# On extrait les segments qui se trouvent dans un polygone de route
tileroadsmap = 'walous_temp_roads_tile_%i' % os.getpid()

gscript.run_command('v.select',
                    ain=ROADSMAP,
                    bin_=region_vector,
                    output=tileroadsmap,
                    flags='t',
                    overwrite=True,
                    quiet=QUIET)

findinfo = gscript.find_file(tileroadsmap,
                             element='vector',
                             mapset=mapset)

if findinfo['name']:


    roads_overlay_map = 'tile_%i_and_roads' % TUILE
    gscript.run_command('v.select',
                        ain=segs_tile_stats_map,
                        bin_=tileroadsmap,
                        operator=ROADS_OVERLAY_OPERATOR,
                        output=roads_overlay_map,
                        overwrite=True,
                        quiet=QUIET)

    if REMOVE:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=tileroadsmap,
                            flags='f',
                            quiet=QUIET)


    findinfo = gscript.find_file(roads_overlay_map,
                                 element='vector',
                                 mapset=mapset)

    if findinfo['name']:

        # IDENTIFIER CRITERES POUR OMBRES
        first = True
        for raster in BANDS.values():
            raster = raster.split('@')[0]
            raster = raster.replace('.', '_')

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=roads_overlay_map,
                                                 column="%s_mean" % raster,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            if first:
                shadowcondition = "(%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)
                first = False
            else:
                shadowcondition += " AND %s_mean < (%s - %s)" % (raster, average_mean, average_stddev)

        shadowcondition += ')'

        condition = "%s is NULL" % TRAINING_COLUMN
        condition += " AND %s" % shadowcondition

        selcats = gscript.read_command('v.db.select',
                                       map_=roads_overlay_map,
                                       column='cat',
                                       where=condition,
                                       flags='c',
                                       quiet=QUIET).splitlines()

        if len(selcats) > 0:
            sqltempfile = gscript.tempfile()
            with open(sqltempfile, 'w') as fout:
                for cat in selcats:
                    fout.write("UPDATE %s SET %s = 911 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

            gscript.run_command('db.execute',
                                input_=sqltempfile,
                                quiet=QUIET)

            gscript.try_remove(sqltempfile)


        univar_stats = gscript.parse_command('v.db.univar',
                                             map_=roads_overlay_map,
                                             column=ndvi_mean,
                                             where="NOT %s" % shadowcondition,
                                             flags='g',
                                             quiet=QUIET)
        average_mean = univar_stats['mean']
        average_stddev = univar_stats['stddev']

        univar_stats = gscript.parse_command('v.db.univar',
                                             map_=roads_overlay_map,
                                             column=ndvi_stddev,
                                             where="NOT %s" % shadowcondition,
                                             flags='g',
                                             quiet=QUIET)
        stddev_mean = univar_stats['mean']
        stddev_stddev = univar_stats['stddev']

        condition = "%s is NULL" % TRAINING_COLUMN
        condition += " AND NOT %s" % shadowcondition
        condition += " AND %s < 0.1" % ndvi_mean
        condition += " AND %s < %s" % (ndvi_stddev, stddev_mean)
        condition += " AND %s < 150" % mnh_mean

        selcats = gscript.read_command('v.db.select',
                                       map_=roads_overlay_map,
                                       column='cat',
                                       where=condition,
                                       flags='c',
                                       quiet=QUIET).splitlines()
        if len(selcats) > 0:
            sqltempfile = gscript.tempfile()
            with open(sqltempfile, 'w') as fout:
                for cat in selcats:
                    fout.write("UPDATE %s SET %s = 11 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))


            gscript.run_command('db.execute',
                                input_=sqltempfile,
                                quiet=QUIET)

            gscript.try_remove(sqltempfile)

        if REMOVE:
            gscript.run_command('g.remove',
                                type_='vector',
                                name=roads_overlay_map,
                                flags='f',
                                quiet=QUIET)

total_time = time.time() - start_time
gscript.verbose("Routes en %s." % str(total_time))


# SOL IMPERMEABILISE / RAIL

start_time = time.time()
# On extrait les segments qui se trouvent dans un polygone de route
tilerailmap = 'walous_temp_rail_tile_%i' % os.getpid()

gscript.run_command('v.select',
                    ain=RAILMAP,
                    bin_=region_vector,
                    output=tilerailmap,
                    flags='t',
                    overwrite=True,
                    quiet=QUIET)

findinfo = gscript.find_file(tilerailmap,
                             element='vector',
                             mapset=mapset)

if findinfo['name']:


    rail_overlay_map = 'tile_%i_and_rail' % TUILE
    gscript.run_command('v.select',
                        ain=segs_tile_stats_map,
                        bin_=tilerailmap,
                        operator=RAIL_OVERLAY_OPERATOR,
                        output=rail_overlay_map,
                        overwrite=True,
                        quiet=QUIET)

    if REMOVE:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=tilerailmap,
                            flags='f',
                            quiet=QUIET)


    findinfo = gscript.find_file(rail_overlay_map,
                                 element='vector',
                                 mapset=mapset)

    if findinfo['name']:

        # IDENTIFIER CRITERES POUR OMBRES
        first = True
        for raster in BANDS.values():
            raster = raster.split('@')[0]
            raster = raster.replace('.', '_')

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=rail_overlay_map,
                                                 column="%s_mean" % raster,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            if first:
                shadowcondition = "(%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)
                first = False
            else:
                shadowcondition += " AND %s_mean < (%s - %s)" % (raster, average_mean, average_stddev)

        shadowcondition += ')'

        condition = "%s is NULL" % TRAINING_COLUMN
        condition += " AND %s" % shadowcondition

        selcats = gscript.read_command('v.db.select',
                                       map_=rail_overlay_map,
                                       column='cat',
                                       where=condition,
                                       flags='c',
                                       quiet=QUIET).splitlines()

        if len(selcats) > 0:
            sqltempfile = gscript.tempfile()
            with open(sqltempfile, 'w') as fout:
                for cat in selcats:
                    fout.write("UPDATE %s SET %s = 913 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

            gscript.run_command('db.execute',
                                input_=sqltempfile,
                                quiet=QUIET)

            gscript.try_remove(sqltempfile)


        univar_stats = gscript.parse_command('v.db.univar',
                                             map_=rail_overlay_map,
                                             column=ndvi_mean,
                                             where="NOT %s" % shadowcondition,
                                             flags='g',
                                             quiet=QUIET)
        average_mean = univar_stats['mean']
        average_stddev = univar_stats['stddev']

        univar_stats = gscript.parse_command('v.db.univar',
                                             map_=rail_overlay_map,
                                             column=ndvi_stddev,
                                             where="NOT %s" % shadowcondition,
                                             flags='g',
                                             quiet=QUIET)
        stddev_mean = univar_stats['mean']
        stddev_stddev = univar_stats['stddev']

        condition = "%s is NULL" % TRAINING_COLUMN
        condition += " AND NOT %s" % shadowcondition
        condition += " AND %s < 0.1" % ndvi_mean
        condition += " AND %s < %s" % (ndvi_stddev, stddev_mean)
        condition += " AND %s < 150" % mnh_mean
        condition += " AND (area*0.25*0.25) < 250"

        selcats = gscript.read_command('v.db.select',
                                       map_=rail_overlay_map,
                                       column='cat',
                                       where=condition,
                                       flags='c',
                                       quiet=QUIET).splitlines()
        if len(selcats) > 0:
            sqltempfile = gscript.tempfile()
            with open(sqltempfile, 'w') as fout:
                for cat in selcats:
                    fout.write("UPDATE %s SET %s = 13 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))


            gscript.run_command('db.execute',
                                input_=sqltempfile,
                                quiet=QUIET)

            gscript.try_remove(sqltempfile)

        if REMOVE:
            gscript.run_command('g.remove',
                                type_='vector',
                                name=rail_overlay_map,
                                flags='f',
                                quiet=QUIET)

total_time = time.time() - start_time
gscript.verbose("Rail en %s." % str(total_time))

# VEGETATION HERBACEE ET SOLS NUS DANS SIGEC
start_time = time.time()
tilefieldsmap = 'walous_temp_fields_tile_%i' % os.getpid()

gscript.run_command('v.clip',
                    input_=FIELDSMAP,
                    output=tilefieldsmap,
                    flags='r',
                    overwrite=True,
                    quiet=QUIET)

topoinfo = gscript.vector_info_topo(tilefieldsmap)
if topoinfo['areas'] > 0:

    fields_overlay_map = 'tile_%i_and_fields' % TUILE
    
    gscript.run_command('v.overlay',
                        ain=segs_tile_stats_map,
                        bin_=tilefieldsmap,
                        out=fields_overlay_map,
                        op='and',
                        overwrite=True,
                        quiet=QUIET)

    if REMOVE:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=tilefieldsmap,
                            flags='f',
                            quiet=QUIET)

    topoinfo = gscript.vector_info_topo(fields_overlay_map)
    if topoinfo['areas'] > 0:

        # IDENTIFIER CRITERES POUR OMBRES
        first = True
        for raster in BANDS.values():
            raster = raster.split('@')[0]
            raster = raster.replace('.', '_')

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=fields_overlay_map,
                                                 column="a_%s_mean" % raster,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            if first:
                overlay_shadowcondition = "(a_%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)
                first = False
            else:
                overlay_shadowcondition += " AND a_%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)

        overlay_shadowcondition += ')'


        gscript.run_command('v.db.addcolumn',
                            map_=fields_overlay_map,
                            column='newarea double precision',
                            quiet=QUIET)

        gscript.run_command('v.to.db',
                            map_=fields_overlay_map,
                            option='area',
                            column='newarea',
                            quiet=QUIET)


        # OMBRES

        shadowsegnb = gscript.read_command('v.db.select',
                                           map_=fields_overlay_map,
                                           column='count(*)',
                                           flags='c',
                                           where="%s" % overlay_shadowcondition,
                                           quiet=QUIET)

        if int(shadowsegnb) > 0:

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=fields_overlay_map,
                                                 column=overlay_ndvi_mean,
                                                 where="%s" % overlay_shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            # VEGETATION BASSE
            condition = "%s is NULL" % overlay_TRAINING_COLUMN
            condition += " AND %s" % overlay_shadowcondition
            condition += " AND newarea/(a_area*0.25*0.25)>0.95"
            condition += " AND %s > (%s - 2.5*%s)" % (overlay_ndvi_mean, average_mean, average_stddev)

            selcats = gscript.read_command('v.db.select',
                                           map_=fields_overlay_map,
                                           column='a_cat',
                                           where=condition,
                                           flags='c',
                                           quiet=QUIET).splitlines()

            if len(selcats) > 0:
                sqltempfile = gscript.tempfile()
                with open(sqltempfile, 'w') as fout:
                    for cat in selcats:
                        fout.write("UPDATE %s SET %s = 905 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))


                gscript.run_command('db.execute',
                                    input_=sqltempfile,
                                    quiet=QUIET)

                gscript.try_remove(sqltempfile)

            # SOLS NUS
            condition = "%s is NULL" % overlay_TRAINING_COLUMN
            condition += " AND %s" % overlay_shadowcondition
            condition += " AND newarea/(a_area*0.25*0.25)>0.95"
            condition += " AND %s < (%s - 2.5*%s)" % (overlay_ndvi_mean, average_mean, average_stddev)

            selcats = gscript.read_command('v.db.select',
                                           map_=fields_overlay_map,
                                           column='a_cat',
                                           where=condition,
                                           flags='c',
                                           quiet=QUIET).splitlines()

            if len(selcats) > 0:
                sqltempfile = gscript.tempfile()
                with open(sqltempfile, 'w') as fout:
                    for cat in selcats:
                        fout.write("UPDATE %s SET %s = 902 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

                gscript.run_command('db.execute',
                                    input_=sqltempfile,
                                    quiet=QUIET)

                gscript.try_remove(sqltempfile)


        # PAS OMBRE

        # VEGETATION BASSE
        shadowsegnb = gscript.read_command('v.db.select',
                                           map_=fields_overlay_map,
                                           column='count(*)',
                                           flags='c',
                                           where="NOT %s" % overlay_shadowcondition,
                                           quiet=QUIET)

        if int(shadowsegnb) > 0:

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=fields_overlay_map,
                                                 column=overlay_ndvi_mean,
                                                 where="NOT %s" % overlay_shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=fields_overlay_map,
                                                 column=overlay_ndvi_stddev,
                                                 where="NOT %s" % overlay_shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)
            stddev_mean = univar_stats['mean']
            stddev_stddev = univar_stats['stddev']

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=fields_overlay_map,
                                                 column=overlay_mnh_mean,
                                                 where="NOT %s" % overlay_shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)
            mnh_stats_mean = univar_stats['mean']
            mnh_stats_stddev = univar_stats['stddev']


            condition = "%s is NULL" % overlay_TRAINING_COLUMN
            condition += " AND NOT %s" % overlay_shadowcondition
            condition += " AND newarea/(a_area*0.25*0.25)>0.95"
            condition += " AND %s > (%s - 2.5*%s)" % (overlay_ndvi_mean, average_mean, average_stddev)
            condition += " AND %s < %s" % (overlay_ndvi_stddev, stddev_mean)
            condition += " AND %s < 100" % overlay_mnh_mean

            selcats = gscript.read_command('v.db.select',
                                           map_=fields_overlay_map,
                                           column='a_cat',
                                           where=condition,
                                           flags='c',
                                           quiet=QUIET).splitlines()

            if len(selcats) > 0:
                sqltempfile = gscript.tempfile()
                with open(sqltempfile, 'w') as fout:
                    for cat in selcats:
                        fout.write("UPDATE %s SET %s = 5 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

                gscript.run_command('db.execute',
                                    input_=sqltempfile,
                                    quiet=QUIET)

                gscript.try_remove(sqltempfile)


            # SOLS NUS

            condition = "%s is NULL" % overlay_TRAINING_COLUMN
            condition += " AND NOT %s" % overlay_shadowcondition
            condition += " AND newarea/(a_area*0.25*0.25)>0.95"
            condition += " AND %s < (%s - 2.5*%s)" % (overlay_ndvi_mean, average_mean, average_stddev)
            condition += " AND %s < 100" % overlay_mnh_mean

            selcats = gscript.read_command('v.db.select',
                                           map_=fields_overlay_map,
                                           column='a_cat',
                                           where=condition,
                                           flags='c',
                                           quiet=QUIET).splitlines()

            if len(selcats) > 0:
                sqltempfile = gscript.tempfile()
                with open(sqltempfile, 'w') as fout:
                    for cat in selcats:
                        fout.write("UPDATE %s SET %s = 21 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

                gscript.run_command('db.execute',
                                    input_=sqltempfile,
                                    quiet=QUIET)

                gscript.try_remove(sqltempfile)

        if REMOVE:
            gscript.run_command('g.remove',
                                type_='vector',
                                name=fields_overlay_map,
                                flags='f',
                                quiet=QUIET)

total_time = time.time() - start_time
gscript.verbose("Végétation et sols nus en %s." % str(total_time))

start_time = time.time()
# TERRE ARABLE
'''
tilearablemap = 'walous_temp_arable_tile_%i' % os.getpid()
arable_overlay_map = 'tile_%i_and_arable' % TUILE

gscript.run_command('v.clip',
                    input_=ARABLESMAP,
                    output=tilearablemap,
                    flags='r',
                    overwrite=True,
                    quiet=QUIET)

topoinfo = gscript.vector_info_topo(tilearablemap)
if topoinfo['areas'] > 0:

    gscript.run_command('v.select',
                        ain=segs_tile_stats_map,
                        bin_=tilearablemap,
                        operator='within',
                        output=arable_overlay_map,
                        overwrite=True,
                        quiet=QUIET)

    if REMOVE:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=tilearablemap,
                            flags='f',
                            quiet=QUIET)

    findinfo = gscript.find_file(arable_overlay_map,
                                 element='vector',
                                 mapset=mapset)

    if findinfo['name']:

        selcats = gscript.read_command('v.db.select',
                                       map_=arable_overlay_map,
                                       column='cat',
                                       flags='c',
                                       quiet=QUIET).splitlines()

        if len(selcats) > 0:
            sqltempfile = gscript.tempfile()
            with open(sqltempfile, 'w') as fout:
                for cat in selcats:
                    sql_expression = "UPDATE %s SET %s =" % (segs_tile_stats_map, TRAINING_COLUMN)
                    sql_expression += " (CASE" 
                    sql_expression += " WHEN %s = 21 THEN 32" % TRAINING_COLUMN
                    sql_expression += " WHEN %s = 5 THEN 35" % TRAINING_COLUMN
                    sql_expression += " WHEN %s = 902 THEN 932" % TRAINING_COLUMN
                    sql_expression += " WHEN %s = 905 THEN 935" % TRAINING_COLUMN
                    sql_expression += " WHEN %s IS NULL AND %s THEN 930" % (TRAINING_COLUMN, shadowcondition)
                    sql_expression += " WHEN %s IS NULL AND NOT %s THEN 30" % (TRAINING_COLUMN, shadowcondition)
                    sql_expression += " ELSE NULL END)"
                    sql_expression += " WHERE cat = %s;\n" % cat
                    fout.write(sql_expression)

            gscript.run_command('db.execute',
                                input_=sqltempfile,
                                quiet=QUIET)

            gscript.try_remove(sqltempfile)

        if REMOVE:
            gscript.run_command('g.remove',
                                type_='vector',
                                name=arable_overlay_map,
                                flags='f',
                                quiet=QUIET)

total_time = time.time() - start_time
gscript.verbose("Terre arable en %s." % str(total_time))
'''

start_time = time.time()

# SOLS NUS DANS CARRIERES
tilequarrymap = 'walous_temp_quarry_tile_%i' % os.getpid()
quarry_overlay_map = 'tile_%i_and_quarry' % TUILE

gscript.run_command('v.clip',
                    input_=QUARRYMAP,
                    output=tilequarrymap,
                    flags='r',
                    overwrite=True,
                    quiet=QUIET)

topoinfo = gscript.vector_info_topo(tilequarrymap)
if topoinfo['areas'] > 0:

    gscript.run_command('v.select',
                        ain=segs_tile_stats_map,
                        bin_=tilequarrymap,
                        operator='within',
                        output=quarry_overlay_map,
                        overwrite=True,
                        quiet=QUIET)

    if REMOVE:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=tilequarrymap,
                            flags='f',
                            quiet=QUIET)

    findinfo = gscript.find_file(quarry_overlay_map,
                                 element='vector',
                                 mapset=mapset)


    if findinfo['name']:

        # IDENTIFIER CRITERES POUR OMBRES
        first = True
        for raster in BANDS.values():
            raster = raster.split('@')[0]
            raster = raster.replace('.', '_')

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=quarry_overlay_map,
                                                 column="%s_mean" % raster,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            if first:
                shadowcondition = "(%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)
                first = False
            else:
                shadowcondition += " AND %s_mean < (%s - %s)" % (raster, average_mean, average_stddev)

        shadowcondition += ')'

        shadowsegnb = gscript.read_command('v.db.select',
                                           map_=quarry_overlay_map,
                                           column='count(*)',
                                           flags='c',
                                           where="NOT %s" % shadowcondition,
                                           quiet=QUIET)

        if int(shadowsegnb) > 0:

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=quarry_overlay_map,
                                                 column=ndvi_mean,
                                                 flags='g',
                                                 quiet=QUIET)
            ndvi_stats_mean = univar_stats['mean']
            ndvi_stats_stddev = univar_stats['stddev']


            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=quarry_overlay_map,
                                                 column=ndwi_mean,
                                                 flags='g',
                                                 quiet=QUIET)

            ndwi_stats_mean = univar_stats['mean']
            ndwi_stats_stddev = univar_stats['stddev']

            condition = "%s is NULL" % TRAINING_COLUMN
            condition += " AND NOT %s" % shadowcondition
            condition += " AND %s < (%s + %s/2)" % (ndvi_mean, ndvi_stats_mean, ndvi_stats_stddev)
            condition += " AND %s < (%s + %s/2)" % (ndwi_mean, ndwi_stats_mean, ndwi_stats_stddev) 
            condition += " AND %s < 100" % mnh_mean

            selcats = gscript.read_command('v.db.select',
                                           map_=quarry_overlay_map,
                                           column='cat',
                                           where=condition,
                                           flags='c',
                                           quiet=QUIET).splitlines()

            if len(selcats) > 0:
                sqltempfile = gscript.tempfile()
                with open(sqltempfile, 'w') as fout:
                    for cat in selcats:
                        fout.write("UPDATE %s SET %s = 22 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

                gscript.run_command('db.execute',
                                    input_=sqltempfile,
                                    quiet=QUIET)

                gscript.try_remove(sqltempfile)

            if REMOVE:
                gscript.run_command('g.remove',
                                    type_='vector',
                                    name=quarry_overlay_map,
                                    flags='f',
                                    quiet=QUIET)

total_time = time.time() - start_time
gscript.verbose("Carrières en %s." % str(total_time))

#FORETS
# Sélectionner les segments qui tombent à l'intérieur des zones forêts connues
# CONIFERES
conif_start_time = time.time()
tileconiferesmap = 'walous_temp_coniferes_tile_%i' % os.getpid()
coniferes_overlay_map = 'tile_%i_and_coniferes' % TUILE

start_time = time.time()
gscript.run_command('v.clip',
                    input_=CONIFEROUSMAP,
                    output=tileconiferesmap,
                    flags='r',
                    overwrite=True,
                    quiet=QUIET)

total_time = time.time() - start_time
gscript.verbose("Region v.clip en %s." % str(total_time))

topoinfo = gscript.vector_info_topo(tileconiferesmap)
if topoinfo['areas'] > 0:

    start_time = time.time()
    gscript.run_command('v.select',
                        ain=segs_tile_stats_map,
                        bin_=tileconiferesmap,
                        operator='within',
                        output=coniferes_overlay_map,
                        overwrite=True,
                        quiet=QUIET)

    total_time = time.time() - start_time
    gscript.verbose("v.select en %s." % str(total_time))

    if REMOVE:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=tileconiferesmap,
                            flags='f',
                            quiet=QUIET)

    findinfo = gscript.find_file(coniferes_overlay_map,
                                 element='vector',
                                 mapset=mapset)

    if findinfo['name']:

        # IDENTIFIER CRITERES POUR OMBRES
        first = True
        for raster in BANDS.values():
            raster = raster.split('@')[0]
            raster = raster.replace('.', '_')

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=coniferes_overlay_map,
                                                 column="%s_mean" % raster,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            if first:
                shadowcondition = "(%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)
                first = False
            else:
                shadowcondition += " AND %s_mean < (%s - %s)" % (raster, average_mean, average_stddev)

        shadowcondition += ')'

        start_time = time.time()
        condition = "%s is NULL" % TRAINING_COLUMN
        condition += " AND %s" % shadowcondition

        selcats = gscript.read_command('v.db.select',
                                       map_=coniferes_overlay_map,
                                       column='cat',
                                       where=condition,
                                       flags='c',
                                       quiet=QUIET).splitlines()

        total_time = time.time() - start_time
        gscript.verbose("v.db.select en %s." % str(total_time))

        start_time = time.time()
        if len(selcats) > 0:
            sqltempfile = gscript.tempfile()
            with open(sqltempfile, 'w') as fout:
                for cat in selcats:
                    fout.write("UPDATE %s SET %s = 941 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

            gscript.run_command('db.execute',
                                input_=sqltempfile,
                                quiet=QUIET)

            gscript.try_remove(sqltempfile)
            total_time = time.time() - start_time
            gscript.verbose("db.execute en %s." % str(total_time))


        # PAS OMBRES
        start_time = time.time()
        shadowsegnb = gscript.read_command('v.db.select',
                                           map_=coniferes_overlay_map,
                                           column='count(*)',
                                           flags='c',
                                           where="NOT %s" % shadowcondition,
                                           quiet=QUIET)

        if int(shadowsegnb) > 0:

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=coniferes_overlay_map,
                                                 column=ndvi_mean,
                                                 where="NOT %s" % shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=coniferes_overlay_map,
                                                 column=mnh_mean,
                                                 where="NOT %s" % shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)
            mnh_stats_mean = univar_stats['mean']
            mnh_stats_stddev = univar_stats['stddev']

            total_time = time.time() - start_time
            gscript.verbose("v.db.univar en %s." % str(total_time))

            start_time = time.time()
            condition = "%s is NULL" % TRAINING_COLUMN
            condition += " AND NOT %s" % shadowcondition
            condition += " AND %s > 300" % mnh_mean
            condition += " AND %s > (%s - 2*%s)" % (ndvi_mean, average_mean, average_stddev)

            selcats = gscript.read_command('v.db.select',
                                           map_=coniferes_overlay_map,
                                           column='cat',
                                           where=condition,
                                           flags='c',
                                           quiet=QUIET).splitlines()

            total_time = time.time() - start_time
            gscript.verbose("v.db.select en %s." % str(total_time))

            start_time = time.time()
            if len(selcats) > 0:
                sqltempfile = gscript.tempfile()
                with open(sqltempfile, 'w') as fout:
                    for cat in selcats:
                        fout.write("UPDATE %s SET %s = 41 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

                gscript.run_command('db.execute',
                                    input_=sqltempfile,
                                    quiet=QUIET)

                gscript.try_remove(sqltempfile)
                total_time = time.time() - start_time
                gscript.verbose("db.execute en %s." % str(total_time))


        if REMOVE:
            gscript.run_command('g.remove',
                                type_='vector',
                                name=coniferes_overlay_map,
                                flags='f',
                                quiet=QUIET)

total_time = time.time() - conif_start_time
gscript.verbose("coniferes en %s." % str(total_time))


# FEUILLUS
feuil_start_time = time.time()
tilefeuillusmap = 'walous_temp_feuillus_tile_%i' % os.getpid()
feuillus_overlay_map = 'tile_%i_and_feuillus' % TUILE

start_time = time.time()
gscript.run_command('v.clip',
                    input_=DECIDUOUSMAP,
                    output=tilefeuillusmap,
                    flags='r',
                    overwrite=True,
                    quiet=QUIET)

total_time = time.time() - start_time
gscript.verbose("Region v.clip en %s." % str(total_time))

topoinfo = gscript.vector_info_topo(tilefeuillusmap)
if topoinfo['areas'] > 0:

    start_time = time.time()
    gscript.run_command('v.select',
                        ain=segs_tile_stats_map,
                        bin_=tilefeuillusmap,
                        operator='within',
                        output=feuillus_overlay_map,
                        overwrite=True,
                        quiet=QUIET)

    total_time = time.time() - start_time
    gscript.verbose("v.select en %s." % str(total_time))

    if REMOVE:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=tilefeuillusmap,
                            flags='f',
                            quiet=QUIET)

    findinfo = gscript.find_file(feuillus_overlay_map,
                                 element='vector',
                                 mapset=mapset)

    if findinfo['name']:

        # IDENTIFIER CRITERES POUR OMBRES
        first = True
        for raster in BANDS.values():
            raster = raster.split('@')[0]
            raster = raster.replace('.', '_')

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=feuillus_overlay_map,
                                                 column="%s_mean" % raster,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            if first:
                shadowcondition = "(%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)
                first = False
            else:
                shadowcondition += " AND %s_mean < (%s - %s)" % (raster, average_mean, average_stddev)

        shadowcondition += ')'

        start_time = time.time()
        condition = "%s is NULL" % TRAINING_COLUMN
        condition += " AND %s" % shadowcondition
        condition += " AND %s > 300" % mnh_mean
        condition += " AND %s > (%s - 2*%s)" % (ndvi_mean, average_mean, average_stddev)

        selcats = gscript.read_command('v.db.select',
                                       map_=feuillus_overlay_map,
                                       column='cat',
                                       where=condition,
                                       flags='c',
                                       quiet=QUIET).splitlines()

        total_time = time.time() - start_time
        gscript.verbose("v.db.select en %s." % str(total_time))

        start_time = time.time()
        if len(selcats) > 0:
            sqltempfile = gscript.tempfile()
            with open(sqltempfile, 'w') as fout:
                for cat in selcats:
                    fout.write("UPDATE %s SET %s = 942 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

            gscript.run_command('db.execute',
                                input_=sqltempfile,
                                quiet=QUIET)

            gscript.try_remove(sqltempfile)
            total_time = time.time() - start_time
            gscript.verbose("db.execute en %s." % str(total_time))

        # PAS OMBRES
        start_time = time.time()
        shadowsegnb = gscript.read_command('v.db.select',
                                           map_=feuillus_overlay_map,
                                           column='count(*)',
                                           flags='c',
                                           where="NOT %s" % shadowcondition,
                                           quiet=QUIET)

        if int(shadowsegnb) > 0:

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=feuillus_overlay_map,
                                                 column=ndvi_mean,
                                                 where="NOT %s" % shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=feuillus_overlay_map,
                                                 column=mnh_mean,
                                                 where="NOT %s" % shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)
            mnh_stats_mean = univar_stats['mean']
            mnh_stats_stddev = univar_stats['stddev']

            total_time = time.time() - start_time
            gscript.verbose("v.db.univar en %s." % str(total_time))

            start_time = time.time()
            condition = "%s is NULL" % TRAINING_COLUMN
            condition += " AND NOT %s" % shadowcondition
            condition += " AND %s > 300" % mnh_mean
            condition += " AND %s > (%s - 2*%s)" % (ndvi_mean, average_mean, average_stddev)

            selcats = gscript.read_command('v.db.select',
                                           map_=feuillus_overlay_map,
                                           column='cat',
                                           where=condition,
                                           flags='c',
                                           quiet=QUIET).splitlines()

            total_time = time.time() - start_time
            gscript.verbose("v.db.select en %s." % str(total_time))

            start_time = time.time()
            if len(selcats) > 0:
                sqltempfile = gscript.tempfile()
                with open(sqltempfile, 'w') as fout:
                    for cat in selcats:
                        fout.write("UPDATE %s SET %s = 42 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

                gscript.run_command('db.execute',
                                    input_=sqltempfile,
                                    quiet=QUIET)

                gscript.try_remove(sqltempfile)
                total_time = time.time() - start_time
                gscript.verbose("db.execute en %s." % str(total_time))


        if REMOVE:
            gscript.run_command('g.remove',
                                type_='vector',
                                name=feuillus_overlay_map,
                                flags='f',
                                quiet=QUIET)

total_time = time.time() - feuil_start_time
gscript.verbose("Feuillus en %s." % str(total_time))


# EAU

start_time = time.time()
tilewatermap = 'walous_temp_water_tile_%i' % os.getpid()

gscript.run_command('v.select',
                    ain=WATERMAP,
                    bin_=region_vector,
                    output=tilewatermap,
                    flags='t',
                    overwrite=True,
                    quiet=QUIET)

findinfo = gscript.find_file(tilewatermap,
                             element='vector',
                             mapset=mapset)

if findinfo['name']:

    water_overlay_map = 'tile_%i_and_water' % TUILE

    # Sélectionner segments dont plus de 90% de la surface tombent dans les
    # bâtiments rétrécis 
    # a_area (from r.object.geometry) is calculated in pixels so we have to 
    # adjust by pixel size
    gscript.run_command('v.overlay',
                        ain=segs_tile_stats_map,
                        bin_=tilewatermap,
                        out=water_overlay_map,
                        op='and',
                        overwrite=True,
                        quiet=QUIET)

    if REMOVE:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=tilewatermap,
                            flags='f',
                            quiet=QUIET)

    # Test whether there are any areas in the results, if not go on to next class
    topoinfo = gscript.vector_info_topo(water_overlay_map)

    if topoinfo['areas'] > 0:

        # IDENTIFIER CRITERES POUR OMBRES
        first = True
        for raster in BANDS.values():
            raster = raster.split('@')[0]
            raster = raster.replace('.', '_')

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=water_overlay_map,
                                                 column="a_%s_mean" % raster,
                                                 flags='g',
                                                 quiet=QUIET)
            average_mean = univar_stats['mean']
            average_stddev = univar_stats['stddev']

            if first:
                overlay_shadowcondition = "(a_%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)
                first = False
            else:
                overlay_shadowcondition += " AND a_%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)

        overlay_shadowcondition += ')'

        gscript.run_command('v.db.addcolumn',
                            map_=water_overlay_map,
                            column='newarea double precision',
                            quiet=QUIET)

        gscript.run_command('v.to.db',
                            map_=water_overlay_map,
                            option='area',
                            column='newarea',
                            quiet=QUIET)

        shadowsegnb = gscript.read_command('v.db.select',
                                           map_=water_overlay_map,
                                           column='count(*)',
                                           flags='c',
                                           where="%s" % overlay_shadowcondition,
                                           quiet=QUIET)

        if int(shadowsegnb) > 0:

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=water_overlay_map,
                                                 column=overlay_ndwi_mean,
                                                 where="%s" % overlay_shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)

            ndwi_stats_mean = univar_stats['mean']
            ndwi_stats_stddev = univar_stats['stddev']

            condition = "%s is NULL" % overlay_TRAINING_COLUMN
            condition += " AND %s" % overlay_shadowcondition
            condition += " AND %s > (%s - %s) " % (overlay_ndwi_mean, ndwi_stats_mean, ndwi_stats_stddev)
            condition += " AND newarea/(a_area*0.25*0.25) > 0.9"

            selcats = gscript.read_command('v.db.select',
                                           map_=water_overlay_map,
                                           column='a_cat',
                                           where=condition,
                                           flags='c',
                                           quiet=QUIET).splitlines()

            if len(selcats) > 0:
                sqltempfile = gscript.tempfile()
                with open(sqltempfile, 'w') as fout:
                    for cat in selcats:
                        fout.write("UPDATE %s SET %s = 906 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

                gscript.run_command('db.execute',
                                    input_=sqltempfile,
                                    quiet=QUIET)

            gscript.try_remove(sqltempfile)

        # PAS OMBRES
        shadowsegnb = gscript.read_command('v.db.select',
                                           map_=water_overlay_map,
                                           column='count(*)',
                                           flags='c',
                                           where="NOT %s" % overlay_shadowcondition,
                                           quiet=QUIET)

        if int(shadowsegnb) > 0:

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=water_overlay_map,
                                                 column=overlay_ndvi_mean,
                                                 where="NOT %s" % overlay_shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)
            ndvi_stats_mean = univar_stats['mean']
            ndvi_stats_stddev = univar_stats['stddev']

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=water_overlay_map,
                                                 column=overlay_ndwi_mean,
                                                 where="NOT %s" % overlay_shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)

            ndwi_stats_mean = univar_stats['mean']
            ndwi_stats_stddev = univar_stats['stddev']

            univar_stats = gscript.parse_command('v.db.univar',
                                                 map_=water_overlay_map,
                                                 column=overlay_nir_mean,
                                                 where="NOT %s" % overlay_shadowcondition,
                                                 flags='g',
                                                 quiet=QUIET)

            nir_stats_mean = univar_stats['mean']
            nir_stats_stddev = univar_stats['stddev']

            condition = "%s is NULL" % overlay_TRAINING_COLUMN
            condition += " AND NOT %s" % overlay_shadowcondition
            condition += " AND newarea/(a_area*0.25*0.25) > 0.95"
            condition += " AND %s > (%s - %s) " % (overlay_ndwi_mean, ndwi_stats_mean, ndwi_stats_stddev)
            condition += " AND %s < (%s - %s)" % (overlay_ndvi_mean, ndvi_stats_mean, ndvi_stats_stddev)
            condition += " AND %s < (%s - %s)" % (overlay_nir_mean, nir_stats_mean, nir_stats_stddev)
            condition += " AND %s < 100" % overlay_mnh_mean

            selcats = gscript.read_command('v.db.select',
                                           map_=water_overlay_map,
                                           column='a_cat',
                                           where=condition,
                                           flags='c',
                                           quiet=QUIET).splitlines()

            if len(selcats) > 0:
                sqltempfile = gscript.tempfile()
                with open(sqltempfile, 'w') as fout:
                    for cat in selcats:
                        fout.write("UPDATE %s SET %s = 6 WHERE cat = %s;\n" % (segs_tile_stats_map, TRAINING_COLUMN, cat))

                gscript.run_command('db.execute',
                                    input_=sqltempfile,
                                    quiet=QUIET)

                gscript.try_remove(sqltempfile)

    if REMOVE:
        gscript.run_command('g.remove',
                            type_='vector',
                            name=water_overlay_map,
                            flags='f',
                            quiet=QUIET)

total_time = time.time() - start_time
gscript.verbose("Eau en %s." % str(total_time))

start_time = time.time()


# OMBRES NON THEMATIQUES

# IDENTIFIER CRITERES POUR OMBRES
first = True
for raster in BANDS.values():
    raster = raster.split('@')[0]
    raster = raster.replace('.', '_')

    univar_stats = gscript.parse_command('v.db.univar',
                                         map_=segs_tile_stats_map,
                                         column="%s_mean" % raster,
                                         flags='g',
                                         quiet=QUIET)
    average_mean = univar_stats['mean']
    average_stddev = univar_stats['stddev']

    if first:
        shadowcondition = "(%s_mean < (%s - %s)" % (raster, average_mean, average_stddev)
        first = False
    else:
        shadowcondition += " AND %s_mean < (%s - %s)" % (raster, average_mean, average_stddev)

shadowcondition += ')'

condition = "%s is NULL" % TRAINING_COLUMN
condition += " AND %s" % shadowcondition

gscript.run_command('v.db.update',
                    map_=segs_tile_stats_map,
                    column=TRAINING_COLUMN,
                    value=9,
                    where=condition,
                    quiet=QUIET)

total_time = time.time() - start_time
gscript.verbose("Ombres en %s." % str(total_time))


# Sortie des résultats
output_file = OUTPUT_STATS_FILE_PREFIX + str(TUILE) + '.csv'
gscript.run_command('v.db.select',
                   map_=segs_tile_stats_map,
                   file_=os.path.join(RESULTS_DIR, output_file),
                   separator='comma',
                   quiet=True)

if REMOVE:
    gscript.run_command('g.remove',
                        type_='vector',
                        name=region_vector,
                        flags='f',
                        quiet=QUIET)

if VECTOR_REMOVE:
    gscript.run_command('g.remove',
                        type_='vector',
                        name=segs_tile_stats_map,
                        flags='f',
                        quiet=QUIET)

gscript.run_command('g.region',
                    region=initregion,
                    quiet=QUIET)
gscript.run_command('g.remove',
                    type_='region',
                    name=initregion,
                    flags='f',
                    quiet=QUIET)

exec_time = time.time() - total_start_time
gscript.verbose("Finished with tile %i in %s seconds." % (TUILE, exec_time))

