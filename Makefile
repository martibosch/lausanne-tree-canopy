.PHONY: swissimage_tiles train_test_split train_classifiers classify_tiles \
	tree_canopy_map confusion_df

#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

DATA_DIR = data
DATA_RAW_DIR := $(DATA_DIR)/raw
DATA_INTERIM_DIR := $(DATA_DIR)/interim
DATA_PROCESSED_DIR := $(DATA_DIR)/processed

MODELS_DIR = models

CODE_DIR = lausanne_tree_canopy

NOTEBOOKS_DIR = notebooks

## rules
define MAKE_DATA_SUB_DIR
$(DATA_SUB_DIR): | $(DATA_DIR)
	mkdir $$@
endef
$(DATA_DIR):
	mkdir $@
$(foreach DATA_SUB_DIR, \
	$(DATA_RAW_DIR) $(DATA_INTERIM_DIR) $(DATA_PROCESSED_DIR), \
	$(eval $(MAKE_DATA_SUB_DIR)))
$(MODELS_DIR):
	mkdir $@

#################################################################################
# COMMANDS                                                                      #
#################################################################################

#################################################################################
# Utilities to be used in several tasks

## variables
CRS = EPSG:2056


#################################################################################
# Make a tree mosaic

# ## 1. Download SWISSIMAGE
# ### variables
# SWISSIMAGE_FILE_KEY = \
# 	swissimage/1m/lausanne/swissimage1m_latest_lausanne_uhi.tif
# SWISSIMAGE_TIF := $(DATA_RAW_DIR)/swissimage.tif
# #### code
# DOWNLOAD_S3_PY := $(CODE_DIR)/download_s3.py

# ### rules
# $(SWISSIMAGE_TIF): | $(DATA_RAW_DIR)
# 	python $(DOWNLOAD_S3_PY) $(SWISSIMAGE_FILE_KEY) $@

## 1. Split SWISSIMAGE tif into tiles
### variables
SWISSIMAGE_TIF := $(DATA_RAW_DIR)/swissimage.tif
AGGLOM_EXTENT_SHP := $(DATA_RAW_DIR)/agglom-extent.shp
SWISSIMAGE_TILES_DIR := $(DATA_INTERIM_DIR)/swissimage-tiles
SWISSIMAGE_TILES_CSV := $(SWISSIMAGE_TILES_DIR)/swissimage-tiles.csv
#### code
MAKE_SWISSIMAGE_TILES_PY := $(CODE_DIR)/make_swissimage_tiles.py

### rules
$(SWISSIMAGE_TILES_DIR): | $(DATA_INTERIM_DIR)
	mkdir $@
$(SWISSIMAGE_TILES_CSV): $(SWISSIMAGE_TIF) $(AGGLOM_EXTENT_SHP) \
	$(MAKE_SWISSIMAGE_TILES_PY) | $(SWISSIMAGE_TILES_DIR)
	python $(MAKE_SWISSIMAGE_TILES_PY) $< $(AGGLOM_EXTENT_SHP) \
		$(SWISSIMAGE_TILES_DIR) $@
swissimage_tiles: $(SWISSIMAGE_TILES_CSV)

## 2. Compute the train/test split
### variables
SPLIT_CSV := $(SWISSIMAGE_TILES_DIR)/split.csv
NUM_COMPONENTS = 24
NUM_TILE_CLUSTERS = 4

### rules
$(SPLIT_CSV): $(SWISSIMAGE_TILES_CSV)
	detectree train-test-split --img-dir $(SWISSIMAGE_TILES_DIR) \
		--output-filepath $(SPLIT_CSV) \
		--num-components $(NUM_COMPONENTS) \
		--num-img-clusters $(NUM_TILE_CLUSTERS)
train_test_split: $(SPLIT_CSV)

## 3. Make the response tiles

# ### variables
# RESPONSE_TILES_DIR := $(DATA_INTERIM_DIR)/response-tiles
# RESPONSE_TILES_CSV := $(RESPONSE_TILES_DIR)/response-tiles.csv
# #### code
# MAKE_RESPONSE_TILES_PY := $(CODE_TREES_DIR)/make_response_tiles.py

# ### rules
# $(RESPONSE_TILES_DIR): | $(DATA_INTERIM_DIR)
# 	mkdir $@
# $(RESPONSE_TILES_CSV): $(SPLIT_CSV) $(MAKE_RESPONSE_TILES_PY) \
# 	| $(RESPONSE_TILES_DIR)
# 	python $(MAKE_RESPONSE_TILES_PY) $(SPLIT_CSV) $(RESPONSE_TILES_DIR) $@

## 4. Train a classifier for each tile cluster

### variables
RESPONSE_TILES_DIR := $(DATA_INTERIM_DIR)/response-tiles
MODEL_JOBLIB_FILEPATHS := $(foreach CLUSTER_LABEL, \
	$(shell seq 0 $$(($(NUM_TILE_CLUSTERS)-1))), \
	$(MODELS_DIR)/$(CLUSTER_LABEL).joblib)

### rules
$(MODELS_DIR)/%.joblib: | $(MODELS_DIR)
	detectree train-classifier --split-filepath $(SPLIT_CSV) \
		--response-img-dir $(RESPONSE_TILES_DIR) --img-cluster $* \
		--output-filepath $@
train_classifiers: $(MODEL_JOBLIB_FILEPATHS)

## 5. Classify the tiles

### variables
CLASSIFIED_TILES_DIR := $(DATA_INTERIM_DIR)/classified-tiles
CLASSIFIED_TILES_CSV_FILEPATHS := $(foreach CLUSTER_LABEL, \
	$(shell seq 0 $$(($(NUM_TILE_CLUSTERS)-1))), \
	$(CLASSIFIED_TILES_DIR)/$(CLUSTER_LABEL).csv)
#### code
MAKE_CLASSIFIED_TILES_PY := $(CODE_DIR)/make_classified_tiles.py

### rules
$(CLASSIFIED_TILES_DIR): | $(DATA_INTERIM_DIR)
	mkdir $@
$(CLASSIFIED_TILES_DIR)/%.csv: $(MODELS_DIR)/%.joblib \
	$(MAKE_CLASSIFIED_TILES_PY) | $(CLASSIFIED_TILES_DIR)
	python $(MAKE_CLASSIFIED_TILES_PY) $(SPLIT_CSV) $< \
		$(CLASSIFIED_TILES_DIR) $@ --img-cluster $(notdir $(basename $@))
classify_tiles: $(CLASSIFIED_TILES_CSV_FILEPATHS)

## 6. Mosaic the classified and response tiles into a single file

### variables
TREE_CANOPY_TIF := $(DATA_PROCESSED_DIR)/tree-canopy.tif
TEMP_TREE_CANOPY_TIF := $(DATA_PROCESSED_DIR)/temp.tif
TREE_NODATA = 0  # shouldn't be ugly hardcoded like that...

### rules
$(AGGLOM_TREES_TIF): $(RESPONSE_TILES_CSV) $(CLASSIFIED_TILES_CSV_FILEPATHS) \
	| $(DATA_PROCESSED_DIR)
	gdal_merge.py -o $(TEMP_TREE_CANOPY_TIF) -n $(TREE_NODATA) \
		$(wildcard $(CLASSIFIED_TILES_DIR)/*.tif) \
		$(wildcard $(RESPONSE_TILES_DIR)/*.tif)
	gdalwarp -t_srs $(CRS) $(TEMP_TREE_CANOPY_TIF) $@
	rm $(TEMP_TREE_CANOPY_TIF)
tree_canopy_map: $(TREE_CANOPY_TIF)

## 7. Validation - confusion data frame
### variables
VALIDATION_TILES_DIR := $(DATA_INTERIM_DIR)/validation-tiles
CONFUSION_CSV := $(VALIDATION_TILES_DIR)/confusion.csv
#### code
MAKE_CONFUSION_DF_PY := $(CODE_DIR)/make_confusion_df.py

### rules
$(CONFUSION_CSV): $(MODEL_JOBLIB_FILEPATHS)
	python $(MAKE_CONFUSION_DF_PY) $(VALIDATION_TILES_DIR) $(SPLIT_CSV) \
		$(MODELS_DIR) $@
confusion_df: $(CONFUSION_CSV)

#################################################################################
