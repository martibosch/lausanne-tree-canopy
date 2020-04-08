import logging

import click
import detectree as dtr
import joblib as jl
import pandas as pd


@click.command()
@click.argument('split_filepath', type=click.Path(exists=True))
@click.argument('model_filepath', type=click.Path(exists=True))
@click.argument('output_dir', type=click.Path(exists=True))
@click.argument('dst_filepath', type=click.Path())
@click.option('--method', default='cluster-II', required=False)
@click.option('--img-cluster', type=int, required=False)
@click.option('--refine/--no-refine', default=True)
@click.option('--refine-beta', default=10, required=False)
@click.option('--refine-int-rescale', default=10000, required=False)
@click.option('--tree-val', default=255, required=False)
@click.option('--nontree-val', default=0, required=False)
def main(split_filepath, model_filepath, output_dir, dst_filepath, method,
         img_cluster, refine, refine_beta, refine_int_rescale, tree_val,
         nontree_val):
    logger = logging.getLogger(__name__)

    logger.info("classifying tiles for cluster %d with classifier from %s",
                img_cluster, model_filepath)
    split_df = pd.read_csv(split_filepath)
    clf = jl.load(model_filepath)

    pred_imgs = dtr.Classifier(
        tree_val=tree_val,
        nontree_val=nontree_val,
        refine=refine,
        refine_beta=refine_beta,
        refine_int_rescale=refine_int_rescale).classify_imgs(
            split_df,
            output_dir,
            clf=clf,
            method=method,
            img_cluster=img_cluster)

    logger.info("dumped %d classified tiles to %s", len(pred_imgs), output_dir)

    pd.Series(pred_imgs).to_csv(dst_filepath, index=False, header=False)
    logger.info("dumped list of classified tiles to %s", dst_filepath)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    main()
