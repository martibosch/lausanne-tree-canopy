import logging
import os

import click
import detectree as dtr
import geopandas as gpd
import rasterio as rio
from shapely import geometry

LULC_WATER_VAL = 14
SIEVE_SIZE = 10


@click.command()
@click.argument('swissimage_filepath', type=click.Path(exists=True))
@click.argument('agglom_extent_filepath', type=click.Path(exists=True))
@click.argument('dst_tiles_dir', type=click.Path(exists=True))
@click.argument('dst_filepath', type=click.Path())
@click.option('--tile-width', type=int, default=512, required=False)
@click.option('--tile-height', type=int, default=512, required=False)
@click.option('--dst-filename', required=False)
@click.option('--only-full-tiles', default=True, required=False)
@click.option('--keep-empty-tiles', default=False, required=False)
def main(swissimage_filepath, agglom_extent_filepath, dst_tiles_dir,
         dst_filepath, tile_width, tile_height, dst_filename, only_full_tiles,
         keep_empty_tiles):
    logger = logging.getLogger(__name__)
    logger.info("splitting %s into %d x %d tiles", swissimage_filepath,
                tile_width, tile_height)

    img_filepaths = dtr.split_into_tiles(swissimage_filepath,
                                         dst_tiles_dir,
                                         tile_width=tile_width,
                                         tile_height=tile_height,
                                         output_filename=dst_filename,
                                         only_full_tiles=only_full_tiles,
                                         keep_empty_tiles=keep_empty_tiles,
                                         custom_meta={'nodata': 255})
    logger.info("dumped %s tiles to %s", len(img_filepaths), dst_tiles_dir)

    # get only the tiles that intersect the agglomeration extent (not to be
    # confused with the extent's bounding box)
    def bbox_geom_from_img_filepath(img_filepath):
        with rio.open(img_filepath) as src:
            return geometry.box(*src.bounds)

    # with rio.open(agglom_lulc_filepath) as src:
    #     agglom_mask = src.dataset_mask()

    #     if exclude_lake:
    #         lulc_arr = src.read(1)
    #         label_arr = ndi.label(lulc_arr == LULC_WATER_VAL,
    #                               ndi.generate_binary_structure(2, 2))[0]
    #         cluster_label = np.argmax(
    #             np.unique(label_arr, return_counts=True)[1][1:]) + 1
    #         # lake_mask = label_arr == cluster_label
    #         agglom_mask = agglom_mask.astype(bool)
    #         agglom_mask &= label_arr != cluster_label
    #         agglom_mask = features.sieve(agglom_mask.astype(np.uint8),
    #                                      size=SIEVE_SIZE) * 255

    #     agglom_mask_gdf = gpd.GeoDataFrame(geometry=[
    #         geometry.shape([(geom, 1) for geom, val in features.shapes(
    #             agglom_mask, transform=src.transform) if val == 255][0][0])
    #     ],
    #                                        crs=src.crs)
    # select the first item while still having a GeoDataFrame
    agglom_mask_gdf = gpd.read_file(agglom_extent_filepath).iloc[:1]

    with rio.open(swissimage_filepath) as swissimage_src:
        # need to use the deprecated syntax `{'init': 'epsg:2056'}` due to a
        # pyproj bug. See https://bit.ly/3e4kUJL
        tiles_gdf = gpd.GeoDataFrame(img_filepaths,
                                     columns=['img_filepath'],
                                     geometry=list(
                                         map(bbox_geom_from_img_filepath,
                                             img_filepaths)),
                                     crs={
                                         'init': 'epsg:21781'
                                     }).to_crs({'init': agglom_mask_gdf.crs})

    # Stay tuned to https://github.com/geopandas/geopandas/issues/921
    agglom_tiles_ser = gpd.sjoin(tiles_gdf,
                                 agglom_mask_gdf,
                                 op='intersects',
                                 how='inner')['img_filepath']

    tiles_to_rm_ser = tiles_gdf['img_filepath'].loc[
        ~tiles_gdf.index.isin(agglom_tiles_ser.index)]
    for img_filepath in tiles_to_rm_ser:
        os.remove(img_filepath)
    logger.info("removed %d tiles that do not intersect with the extent of %s",
                len(tiles_to_rm_ser), dst_filepath)

    agglom_tiles_ser.to_csv(dst_filepath, index=False, header=False)
    logger.info("dumped list of tile filepaths to %s", dst_filepath)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    main()
