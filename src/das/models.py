"""Defines the network architectures."""
import tensorflow.keras as keras
import tensorflow.keras.layers as kl
from typing import List, Optional
from . import tcn as tcn_layer
from .kapre.time_frequency import Spectrogram


model_dict = dict()


def _register_as_model(func):
    """Adds func to model_dict Dict[modelname: modelfunc]. For selecting models by string."""
    model_dict[func.__name__] = func
    return func


@_register_as_model
def tcn(*args, **kwargs):
    """Synonym for tcn_stft."""
    return tcn_stft(*args, **kwargs)


@_register_as_model
def tcn_stft(nb_freq: int, nb_classes: int, nb_hist: int = 1, nb_filters: int = 16, kernel_size: int = 3,
             nb_conv: int = 1, loss: str = "categorical_crossentropy",
             dilations: Optional[List[int]] = None, activation: str = 'norm_relu',
             use_skip_connections: bool = True, return_sequences: bool = True,
             dropout_rate: float = 0.00, padding: str = 'same', sample_weight_mode: str = None,
             nb_pre_conv: int = 0, pre_nb_dft: int = 64,
             nb_lstm_units: int = 0,
             learning_rate: float = 0.0005, upsample: bool = True,
             use_separable: bool = False,
             **kwignored):
    """Create TCN network with optional trainable STFT layer as pre-processing and downsampling frontend.

    Args:
        nb_freq (int): [description]
        nb_classes (int): [description]
        nb_hist (int, optional): [description]. Defaults to 1.
        nb_filters (int, optional): [description]. Defaults to 16.
        kernel_size (int, optional): [description]. Defaults to 3.
        nb_conv (int, optional): [description]. Defaults to 1.
        loss (str, optional): [description]. Defaults to "categorical_crossentropy".
        dilations (List[int], optional): [description]. Defaults to [1, 2, 4, 8, 16].
        activation (str, optional): [description]. Defaults to 'norm_relu'.
        use_skip_connections (bool, optional): [description]. Defaults to True.
        return_sequences (bool, optional): [description]. Defaults to True.
        dropout_rate (float, optional): [description]. Defaults to 0.00.
        padding (str, optional): [description]. Defaults to 'same'.
        nb_pre_conv (int, optional): If >0 adds a single STFT layer with a hop size of 2**nb_pre_conv before the TCN.
                                     Useful for speeding up training by reducing the sample rate early in the network.
                                     Defaults to 0 (no downsampling)
        pre_nb_dft (int, optional): Duration of filters (in samples) for the STFT frontend.
                                    Number of filters is pre_nb_dft // 2 + 1.
                                    Defaults to 64.
        learning_rate (float, optional) Defaults to 0.0005
        nb_lstm_units (int, optional): Defaults to 0.
        upsample (bool, optional): whether or not to restore the model output to the input samplerate.
                                   Should generally be True during training and evaluation but may speed up inference.
                                   Defaults to True.
        use_separable (bool, optional): use separable convs in residual block. Defaults to False.
        kwignored (Dict, optional): additional kw args in the param dict used for calling m(**params) to be ingonred

    Returns:
        [keras.models.Model]: Compiled TCN network model.
    """
    if dilations is None:
        dilations = [1, 2, 4, 8, 16]
    # if nb_freq > 1:
    #     raise ValueError(f'This model only works with single channel data but last dim of inputs has len {nb_freq} (should be 1).')
    input_layer = kl.Input(shape=(nb_hist, nb_freq))
    out = input_layer

    if nb_pre_conv > 0:
        out = Spectrogram(n_dft=pre_nb_dft, n_hop=2**nb_pre_conv,
                          return_decibel_spectrogram=True, power_spectrogram=1.0,
                          trainable_kernel=True, name='trainable_stft', image_data_format='channels_last')(out)
        out = kl.Reshape((out.shape[1], out.shape[2] * out.shape[3]))(out)

    x = tcn_layer.TCN(nb_filters=nb_filters, kernel_size=kernel_size, nb_stacks=nb_conv, dilations=dilations,
                      activation=activation, use_skip_connections=use_skip_connections, padding=padding,
                      dropout_rate=dropout_rate, return_sequences=return_sequences,
                      use_separable=use_separable)(out)

    if nb_lstm_units > 0:
        x = kl.Bidirectional(kl.LSTM(units=nb_lstm_units, return_sequences=True))(x)

    x = kl.Dense(nb_classes)(x)
    x = kl.Activation('softmax')(x)

    if nb_pre_conv > 0 and upsample:
        x = kl.UpSampling1D(size=2**nb_pre_conv)(x)

    output_layer = x

    model = keras.models.Model(input_layer, output_layer, name='TCN')
    model.compile(optimizer=keras.optimizers.Adam(lr=learning_rate, amsgrad=True, clipnorm=1.),
                  loss=loss, sample_weight_mode=sample_weight_mode)
    return model


@_register_as_model
def tcn_tcn(nb_freq: int, nb_classes: int, nb_hist: int = 1, nb_filters: int = 16, kernel_size: int = 3,
            nb_conv: int = 1, loss: str = "categorical_crossentropy",
            dilations: Optional[List[int]] = None, activation: str = 'norm_relu',
            use_skip_connections: bool = True, return_sequences: bool = True,
            dropout_rate: float = 0.00, padding: str = 'same', sample_weight_mode: str = None,
            nb_pre_conv: int = 0, learning_rate: float = 0.0005, upsample: bool = True,
            use_separable: bool = False,
            **kwignored):
    """Create TCN network with TCN layer as pre-processing and downsampling frontend.

    Args:
        nb_freq (int): [description]
        nb_classes (int): [description]
        nb_hist (int, optional): [description]. Defaults to 1.
        nb_filters (int, optional): [description]. Defaults to 16.
        kernel_size (int, optional): [description]. Defaults to 3.
        nb_conv (int, optional): [description]. Defaults to 1.
        loss (str, optional): [description]. Defaults to "categorical_crossentropy".
        dilations (List[int], optional): [description]. Defaults to [1, 2, 4, 8, 16].
        activation (str, optional): [description]. Defaults to 'norm_relu'.
        use_skip_connections (bool, optional): [description]. Defaults to True.
        return_sequences (bool, optional): [description]. Defaults to True.
        dropout_rate (float, optional): [description]. Defaults to 0.00.
        padding (str, optional): [description]. Defaults to 'same'.
        nb_pre_conv (int, optional): If >0 adds a single TCN layer with a final maxpooling layer
                                     with block size of `2**nb_pre_conv` before the TCN.
                                     Useful for speeding up training by reducing the sample rate early in the network.
                                     Defaults to 0 (no downsampling)
        learning_rate (float, optional) Defaults to 0.0005
        upsample (bool, optional): whether or not to restore the model output to the input samplerate.
                                   Should generally be True during training and evaluation but my speed up inference .
                                   Defaults to True.
        use_separable (bool, optional): use separable convs in residual block. Defaults to False.
        kwignored (Dict, optional): additional kw args in the param dict used for calling m(**params) to be ingonred

    Returns:
        [keras.models.Model]: Compiled TCN network model.
    """
    if dilations is None:
        dilations = [1, 2, 4, 8, 16]

    input_layer = kl.Input(shape=(nb_hist, nb_freq))
    out = input_layer
    if nb_pre_conv > 0:
        out = tcn_layer.TCN(nb_filters=nb_filters, kernel_size=kernel_size, nb_stacks=nb_pre_conv, dilations=dilations,
                            activation=activation, use_skip_connections=use_skip_connections, padding=padding,
                            dropout_rate=dropout_rate, return_sequences=return_sequences,
                            use_separable=use_separable, name='frontend')(out)
        out = kl.MaxPooling1D(pool_size=2**nb_pre_conv, strides=2**nb_pre_conv)(out)  # or avg pooling?

    x = tcn_layer.TCN(nb_filters=nb_filters, kernel_size=kernel_size, nb_stacks=nb_conv, dilations=dilations,
                      activation=activation, use_skip_connections=use_skip_connections, padding=padding,
                      dropout_rate=dropout_rate, return_sequences=return_sequences,
                      use_separable=use_separable)(out)
    x = kl.Dense(nb_classes)(x)
    x = kl.Activation('softmax')(x)
    if nb_pre_conv > 0 and upsample:
        x = kl.UpSampling1D(size=2**nb_pre_conv)(x)
    output_layer = x
    model = keras.models.Model(input_layer, output_layer, name='TCN')

    model.compile(optimizer=keras.optimizers.Adam(lr=learning_rate, amsgrad=True, clipnorm=1.),
                  loss=loss, sample_weight_mode=sample_weight_mode)
    return model
