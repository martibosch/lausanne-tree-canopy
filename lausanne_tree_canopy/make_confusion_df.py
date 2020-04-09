import glob
import logging
from os import path

import click
import detectree as dtr
import joblib as jl
import numpy as np
import pandas as pd
import rasterio as rio
from detectree import settings


@click.command()
@click.argument('validation_img_dir', type=click.Path(exists=True))
@click.argument('split_filepath', type=click.Path(exists=True))
@click.argument('models_dir', type=click.Path(exists=True))
@click.argument('dst_filepath', type=click.Path())
def main(validation_img_dir, split_filepath, models_dir, dst_filepath):
    logger = logging.getLogger(__name__)

    validation_img_filepaths = glob.glob(
        path.join(validation_img_dir, settings.IMG_DEFAULT_FILENAME_PATTERN))

    logger.info("computing confusion data frame with the tiles in %s",
                validation_img_dir)
    split_df = pd.read_csv(split_filepath, index_col=0)
    c = dtr.Classifier()
    observations = []
    predictions = []
    for validation_img_filepath in validation_img_filepaths:
        validation_img_filename = path.basename(validation_img_filepath)
        try:
            img_filepath, img_cluster = split_df[
                split_df['img_filepath'].str.endswith(
                    validation_img_filename)][['img_filepath',
                                               'img_cluster']].iloc[0]
        except IndexError:
            raise ValueError(
                f'Could not find an image named {validation_img_filename} in '
                f' {split_filepath}')
        with rio.open(validation_img_filepath) as src:
            observations.append(src.read(1))
        predictions.append(
            c.classify_img(
                img_filepath,
                jl.load(path.join(models_dir, f'{img_cluster}.joblib'))))

    truth_ser = pd.Series(np.hstack(observations).flatten(), name='obs')
    pred_ser = pd.Series(np.hstack(predictions).flatten(), name='pred')
    df = pd.crosstab(truth_ser, pred_ser) / len(truth_ser)
    logger.info("estimated accuracy score is %f", np.trace(df))

    df.to_csv(dst_filepath)
    logger.info("dumped confusion data frame to %s", dst_filepath)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    main()
