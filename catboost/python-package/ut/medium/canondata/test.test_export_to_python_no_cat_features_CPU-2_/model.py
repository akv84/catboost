###  Model data
class catboost_model(object):
    float_features_index = [
        1, 3, 9, 11, 13, 15, 19, 23, 32, 39, 47,
    ]
    float_feature_count = 48
    cat_feature_count = 0
    binary_feature_count = 11
    tree_count = 2
    float_feature_borders = [
        [0.0622565],
        [0.5],
        [0.5],
        [0.5],
        [0.5],
        [0.98272598],
        [0.5],
        [0.097222149],
        [0.5],
        [0.0010412449],
        [0.60571146]
    ]
    tree_depth = [6, 5]
    tree_split_border = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    tree_split_feature_index = [8, 0, 5, 9, 4, 6, 10, 7, 3, 2, 1]
    tree_split_xor_mask = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    cat_features_index = []
    one_hot_cat_feature_index = []
    one_hot_hash_values = [
    ]
    ctr_feature_borders = [
    ]

    ## Aggregated array of leaf values for trees. Each tree is represented by a separate line:
    leaf_values = [
        0.0007909629375735687, 0.0005249999905005097, 0.00191470584442072, 0, 0.0009313725844463869, 0.001049999981001019, 0, 0, 0.001480637814883255, 0.002774999973736703, 0.001819217596641749, 0.002135000514574336, 0, 0, 0, 0, 0.001424999964237213, 0, 0.001049999981001019, 0, 0, 0, 0, 0, 0.001224999977834523, 0, 0.00305039463412899, 0.002099999962002039, 0, 0, 0, 0, 0.0005876865565304213, 0.00295422133567028, 0, 0, 0, 0, 0, 0, 0.001826086923480034, 0.003670588189538786, 0.002372058927585532, 0.003879166769288062, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0005249999905005097, 0, 0, 0, 0, 0,
        0.0006921719453553643, 0, 0.0004117280956206751, 0, 0.0002214690529509848, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.001420420624297372, 0.003184800622098175, 0.0004887949433514606, 0.002349379335729056, 0.0008775089953256384, 0.0005138952071370965, 0, 0, 0.001868792742743027, 0.003363426897674278, 0.001574119166780254, 0.003566977137765126, 0.0006661870385846651, 0.001839427350751397, 0, 0.0006163558457548979
    ]
cat_features_hashes = {
}

def hash_uint64(string):
    return cat_features_hashes.get(str(string), 0x7fFFffFF)


### Applicator for the CatBoost model

def apply_catboost_model(float_features, cat_features=[], ntree_start=0, ntree_end=catboost_model.tree_count):
    """
    Applies the model built by CatBoost.

    Parameters
    ----------

    float_features : list of float features

    cat_features : list of categorical features
        You need to pass float and categorical features separately in the same order they appeared in train dataset.
        For example if you had features f1,f2,f3,f4, where f2 and f4 were considered categorical, you need to pass here float_features=f1,f3, cat_features=f2,f4


    Returns
    -------
    prediction : formula value for the model and the features

    """
    if ntree_end == 0:
        ntree_end = catboost_model.tree_count
    else:
        ntree_end = min(ntree_end, catboost_model.tree_count)

    model = catboost_model

    assert len(float_features) >= model.float_feature_count
    assert len(cat_features) >= model.cat_feature_count

    # Binarise features
    binary_features = [0] * model.binary_feature_count
    binary_feature_index = 0

    for i in range(len(model.float_feature_borders)):
        for border in model.float_feature_borders[i]:
            binary_features[binary_feature_index] += 1 if (float_features[model.float_features_index[i]] > border) else 0
        binary_feature_index += 1
    transposed_hash = [0] * model.cat_feature_count
    for i in range(model.cat_feature_count):
        transposed_hash[i] = hash_uint64(cat_features[i])

    if len(model.one_hot_cat_feature_index) > 0:
        cat_feature_packed_indexes = {}
        for i in range(model.cat_feature_count):
            cat_feature_packed_indexes[model.cat_features_index[i]] = i
        for i in range(len(model.one_hot_cat_feature_index)):
            cat_idx = cat_feature_packed_indexes[model.one_hot_cat_feature_index[i]]
            hash = transposed_hash[cat_idx]
            for border_idx in range(len(model.one_hot_hash_values[i])):
                binary_features[binary_feature_index] |= (1 if hash == model.one_hot_hash_values[i][border_idx] else 0) * (border_idx + 1)
            binary_feature_index += 1

    if hasattr(model, 'model_ctrs') and model.model_ctrs.used_model_ctrs_count > 0:
        ctrs = [0.] * model.model_ctrs.used_model_ctrs_count;
        calc_ctrs(model.model_ctrs, binary_features, transposed_hash, ctrs)
        for i in range(len(model.ctr_feature_borders)):
            for border in model.ctr_feature_borders[i]:
                binary_features[binary_feature_index] += 1 if ctrs[i] > border else 0
            binary_feature_index += 1

    # Extract and sum values from trees
    result = 0.
    tree_splits_index = 0
    current_tree_leaf_values_index = 0
    for tree_id in range(ntree_start, ntree_end):
        current_tree_depth = model.tree_depth[tree_id]
        index = 0
        for depth in range(current_tree_depth):
            border_val = model.tree_split_border[tree_splits_index + depth]
            feature_index = model.tree_split_feature_index[tree_splits_index + depth]
            xor_mask = model.tree_split_xor_mask[tree_splits_index + depth]
            index |= ((binary_features[feature_index] ^ xor_mask) >= border_val) << depth
        result += model.leaf_values[current_tree_leaf_values_index + index]
        tree_splits_index += current_tree_depth
        current_tree_leaf_values_index += (1 << current_tree_depth)
    return result


