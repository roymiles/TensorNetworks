import tensorflow.compat.v1 as tf
from Layers.layer import ILayer
import Weights.impl.core
import Weights.impl.sandbox
import math
import numpy as np


class SwitchableBatchNormalisationLayer(ILayer):
    def __init__(self, switch_list=[1.0], affine=True):
        raise Exception("Switchable batch norm is not implemented yet")
        """ Implements switchable batch normalisation
            If affine is False, the scale and offset parameters won't be used
            When affine=False the output of BatchNorm is equivalent to considering gamma=1 and beta=0 as constants. """
        super().__init__()
        self._affine = affine
        self._switch_list = switch_list

        self.switchable_fns = []

    def get_switches(self, input, is_training, switch_idx):
        pred_fn_pairs = []
        for sw_idx, sw in enumerate(self._switch_list):
            with tf.variable_scope(f"switch_{sw}"):
                pred_fn_pairs.append((tf.equal(switch_idx, sw_idx),
                                      lambda: tf.layers.batch_normalization(input, training=is_training)))

        return pred_fn_pairs

    def __call__(self, input, is_training, switch_idx, affine=True):

        # TODO: Implement switchable batch norm, but maybe in contrib
        # net = tf.case(self.get_switches(input, is_training, switch_idx),
        #              default=lambda: tf.layers.batch_normalization(input, training=is_training),
        #              exclusive=True)
        # return net

        # Independant batch normalisation (for each switch)
        # with tf.variable_scope(f"switch"):
        net = tf.layers.batch_normalization(input, training=is_training)
        return net


class MobileNetV2BottleNeck(ILayer):
    def __init__(self, in_channels, expansion, filters, build_method=Weights.impl.core, strides=(1, 1), ranks=None,
                 weight_decay=0.00004):
        """
        See: https://towardsdatascience.com/review-mobilenetv2-light-weight-model-image-classification-8febb490e61c

        :param in_channels: Number of input channels
        :param expansion: Expansion factor
        :param filters: Number of output channels
        :param strides: Depthwise stride
        :param ranks: Used if building weights using Graphs. Define the % of input channels/output channels for the
                      expansion and projection kernels
        :param weight_decay: Weight decay for L2 regularisation of expansion and projection weights
        """
        super().__init__()

        px = strides[0]
        py = strides[1]
        self._strides = [1, px, py, 1]
        self._build_method = build_method
        self._in_channels = in_channels
        self._expansion = expansion
        self._filters = filters
        self._ranks = ranks
        self._weight_decay = weight_decay

        super().__init__()

    def get_weight_decay(self):
        return self._weight_decay

    def get_ranks(self):
        return self._ranks

    def create_weights(self):
        return self._build_method.mobilenetv2_bottleneck

    def __call__(self, input, weights, is_training):

        # Expansion layer
        net = tf.nn.conv2d(input, weights.expansion_kernel, strides=[1, 1, 1, 1], padding="SAME")
        net = tf.layers.batch_normalization(net, training=is_training, epsilon=1e-3, momentum=0.999)
        net = tf.nn.relu6(net)

        # Depthwise layer
        net = tf.nn.depthwise_conv2d(net, weights.depthwise_kernel, strides=self._strides, padding="SAME")
        net = tf.layers.batch_normalization(net, training=is_training, epsilon=1e-3, momentum=0.999)
        net = tf.nn.relu6(net)

        # Projection layer (linear)
        net = tf.nn.conv2d(net, weights.projection_kernel, strides=[1, 1, 1, 1], padding="SAME")
        net = tf.layers.batch_normalization(net, training=is_training, epsilon=1e-3, momentum=0.999)

        # Only residual add when strides is 1
        is_residual = True if self._strides == [1, 1, 1, 1] else False
        # is_conv_res = False if net.get_shape().as_list()[3] == input.get_shape().as_list()[3] else True

        if is_residual:

            if net.get_shape().as_list()[3] == input.get_shape().as_list()[3]:
                return net + input
            else:
                return net

        else:
            return net

    def get_filters(self):
        return self._filters

    def get_expansion(self):
        return self._expansion

    def get_in_channels(self):
        return self._in_channels

    def get_strides(self):
        return self._strides

# class OffsetConvolutionLayer(ILayer):
    """
        Factors 
    """


class PointwiseDot(ILayer):
    """
        Potential replacement for pointwise convolution
    """
    def __init__(self, shape, build_method=Weights.impl.sandbox, use_bias=True,
                 kernel_initializer=tf.glorot_normal_initializer(),
                 bias_initializer=tf.zeros_initializer(),
                 kernel_regularizer=None, bias_regularizer=None):

        super().__init__()
        self._shape = shape
        self._build_method = build_method
        self._use_bias = use_bias

        self.kernel_initializer = kernel_initializer
        self.bias_initializer = bias_initializer
        self.kernel_regularizer = kernel_regularizer
        self.bias_regularizer = bias_regularizer

    def create_weights(self):
        return self._build_method.pointwise_dot

    def get_shape(self):
        return self._shape

    def using_bias(self):
        return self._use_bias

    def __call__(self, input, weights, is_training=True):
        # input : B x w x h x c
        # c     : c x r1
        # g     : r1 x r2
        # n     : r2 x n
        net = tf.tensordot(input, weights.c, axes=[3, 0])
        net = tf.layers.batch_normalization(net, training=is_training)
        # No ReLU here?

        # B x w x h x r1
        net = tf.tensordot(net, weights.g, axes=[3, 0])
        net = tf.layers.batch_normalization(net, training=is_training)
        net = tf.nn.relu(net)

        # B x w x h x r2
        net = tf.tensordot(net, weights.n, axes=[3, 0])
        if weights.bias:
            net = tf.nn.bias_add(net, weights.bias)

        net = tf.layers.batch_normalization(net, training=is_training)
        net = tf.nn.relu(net)

        # B x w x h x n
        return net


class PartitionedDepthwiseSeparableLayer(ILayer):
    def __init__(self, shape, strides=(1, 1), use_bias=True, padding="SAME",  # partitions=[0.8, 0.8],
                 partitions=None,
                 kernel_initializer=tf.glorot_normal_initializer(), bias_initializer=tf.zeros_initializer(),
                 kernel_regularizer=None, bias_regularizer=None, ranks=None):
        """
            Custom implementation for the depthwise separable layers

            The pointwise convolution is separated across the input channel dimensions
            Whereas the depthwise + standard convolution
        """
        super().__init__()

        px = strides[0]
        py = strides[1]
        self._strides = [1, px, py, 1]

        # The two partitions
        self.partitions = partitions

        self._shape = shape
        self._padding = padding
        self._use_bias = use_bias

        self.kernel_initializer = kernel_initializer
        self.bias_initializer = bias_initializer
        self.kernel_regularizer = kernel_regularizer
        self.bias_regularizer = bias_regularizer

        # Rank for the core tensor G
        self.ranks = ranks

    def create_weights(self):
        # Only one way to create these weights for now
        return Weights.impl.sandbox.partitioned_depthwise_separable

    def get_shape(self):
        return self._shape

    def using_bias(self):
        return self._use_bias

    def get_strides(self):
        return self._strides

    def __call__(self, input, weights, is_training):
        if weights.conv_kernel is not None:
            # Standard convolution
            size = weights.conv_kernel.get_shape().as_list()[2]  # W x H x C x N
            conv_out = tf.nn.conv2d(input[:, :, :, 0:size], weights.conv_kernel, strides=self._strides, padding=self._padding)
            offset = size
        else:
            offset = 0

        if weights.depthwise_kernel is not None:
            # Depthwise separable stage
            dw_out = tf.nn.depthwise_conv2d(input[:, :, :, offset:], weights.depthwise_kernel, strides=self._strides,
                                            padding=self._padding)

        if weights.conv_kernel is not None and weights.depthwise_kernel is None:
            net = conv_out
        elif weights.depthwise_kernel is not None and weights.conv_kernel is None:
            net = dw_out
        elif weights.conv_kernel is not None and weights.depthwise_kernel is not None:
            # Combine depthwise + standard results
            net = tf.concat([conv_out, dw_out], axis=3)
        else:
            raise Exception("No standard or depthwise kernels.")

        # BN + ReLU
        net = tf.layers.batch_normalization(net, training=is_training)
        net = net * tf.nn.relu6(net + 3) / 6  # HSwish

        # Pointwise
        if weights.pointwise_kernel is not None:
            pw_out = tf.nn.conv2d(net, weights.pointwise_kernel, strides=self._strides, padding=self._padding)

        # Factored pointwise
        if weights.factored_pointwise_kernel is not None:
            fpw_out = tf.nn.conv2d(net, weights.factored_pointwise_kernel, strides=self._strides, padding=self._padding)

        if weights.pointwise_kernel is not None and weights.factored_pointwise_kernel is None:
            net = pw_out
        elif weights.factored_pointwise_kernel is not None and weights.pointwise_kernel is None:
            net = fpw_out
        elif weights.pointwise_kernel is not None and weights.factored_pointwise_kernel is not None:
            # Combine pointwise results
            net = tf.concat([pw_out, fpw_out], axis=3)
        else:
            raise Exception("No pointwise or factored pointwise kernels.")

        # Only residual add when strides is 1
        is_residual = True if self._strides == [1, 1, 1, 1] else False

        if is_residual:
            return tf.concat([net, input], axis=3)
        else:
            return net


class DenseBlock(ILayer):
    def __init__(self, name, in_channels, num_layers, growth_rate, dropout_rate, bottleneck,
                 build_method=Weights.impl.sandbox, ranks=None,
                 kernel_initializer=tf.glorot_normal_initializer(),  bias_initializer=tf.zeros_initializer(),
                 kernel_regularizer=None, bias_regularizer=None):
        """

        :param name: Variable scope
        :param N: How many layers
        """

        super().__init__()
        self.name = name
        self.in_channels = in_channels
        self.num_layers = num_layers
        self.growth_rate = growth_rate
        self.build_method = build_method
        self.dropout_rate = dropout_rate
        self.bottleneck = bottleneck
        self.ranks = ranks

        self.kernel_initializer = kernel_initializer
        self.bias_initializer = bias_initializer
        self.kernel_regularizer = kernel_regularizer
        self.bias_regularizer = bias_regularizer

    def create_weights(self):
        return self.build_method.dense_block

    def add_layer(self, name, input, pointwise_kernel, conv_kernel, is_training):
        with tf.variable_scope(name):
            net = tf.layers.batch_normalization(input, training=is_training)
            net = tf.nn.relu(net)

            # 1x1 conv
            net = tf.nn.conv2d(net, pointwise_kernel, strides=[1, 1, 1, 1], padding="SAME")
            net = tf.layers.dropout(net, rate=self.dropout_rate, training=is_training)
            net = tf.layers.batch_normalization(net, training=is_training)
            net = tf.nn.relu(net)

            # Standard convolution
            net = tf.nn.conv2d(net, conv_kernel, strides=[1, 1, 1, 1], padding="SAME")

            """
            # ---- Group convolution ---- #
            # Apply the group convolution kernels to disjoint sets of the input feature maps
            group_conv_out = []
            in_channels = net.get_shape().as_list()[3]
            group_size = int(in_channels / len(conv_kernel))
            for i, group_conv_kernel in enumerate(conv_kernel):
                offset = i * group_size   # Each of size in_channels / num_groups
                group_conv_out.append(tf.nn.conv2d(net[:, :, :, offset:offset+group_size], group_conv_kernel,
                                                   strides=[1, 1, 1, 1], padding="SAME"))

            # Concatenate the results
            net = tf.concat(group_conv_out, axis=3)
            # -------------------------- #
            """

            # net = tf.nn.depthwise_conv2d(net, conv_kernel, strides=[1, 1, 1, 1], padding="SAME")
            net = tf.layers.dropout(net, rate=self.dropout_rate, training=is_training)
            net = tf.concat([input, net], axis=3)
            return net

    def __call__(self, input, weights, is_training):
        """ weights is just the set of conv weights """
        with tf.variable_scope(self.name):
            net = input
            for i in range(self.num_layers):
                net = self.add_layer(f"composite_layer_{i}", net, weights.pointwise_kernels[i], weights.conv_kernels[i],
                                     is_training)
                # output channels = input channels + growth rate

        return net

