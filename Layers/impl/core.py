import tensorflow as tf
from Layers.layer import ILayer


class ConvLayer(ILayer):
    def __init__(self, shape, strides=(1, 1), use_bias=True, padding="SAME",
                 kernel_initializer=tf.glorot_normal_initializer(), bias_initializer=tf.zeros_initializer(),
                 kernel_regularizer=None, bias_regularizer=None):
        super().__init__()

        px = strides[0]
        py = strides[1]
        self._strides = [1, px, py, 1]

        self._shape = shape
        self._padding = padding
        self._use_bias = use_bias

        # Can't be bothered to make getters for these, just make them public
        self.kernel_initializer = kernel_initializer
        self.bias_initializer = bias_initializer
        self.kernel_regularizer = kernel_regularizer
        self.bias_regularizer = bias_regularizer

    def get_shape(self):
        return self._shape

    def using_bias(self):
        return self._use_bias

    def get_strides(self):
        return self._strides

    def __call__(self, input, kernel, bias=None):
        net = tf.nn.conv2d(input, kernel, strides=self._strides, padding=self._padding)

        if bias:
            net = tf.nn.bias_add(net, bias)

        return net


class ConvLayerConstant(ILayer):
    """ Same as ConvLayer, but fixed, constant filter """
    def __init__(self, kernel, strides=[1, 1, 1, 1], padding="SAME"):
        super().__init__()
        self._kernel = kernel
        self._strides = strides
        self._padding = padding

    def get_kernel(self):
        return self._kernel

    def get_strides(self):
        return self._strides

    def __call__(self, input):
        return tf.nn.conv2d(input, self._kernel, strides=self._strides, padding=self._padding)


class DepthwiseConvLayer(ILayer):
    """ Depthwise convolution
        NOTE: Pointwise convolution uses standard conv layer """
    def __init__(self, shape, strides=(1, 1), use_bias=True, padding="SAME",
                 kernel_initializer=tf.glorot_normal_initializer(), bias_initializer=tf.zeros_initializer(),
                 kernel_regularizer=None, bias_regularizer=None):
        super().__init__()

        px = strides[0]
        py = strides[1]
        self._strides = [1, px, py, 1]

        self._shape = shape
        self._padding = padding
        self._use_bias = use_bias

        self.kernel_initializer = kernel_initializer
        self.bias_initializer = bias_initializer
        self.kernel_regularizer = kernel_regularizer
        self.bias_regularizer = bias_regularizer

    def get_shape(self):
        return self._shape

    def using_bias(self):
        return self._use_bias

    def get_strides(self):
        return self._strides

    def __call__(self, input, kernel, bias=None):
        # Depthwise convolution
        net = tf.nn.depthwise_conv2d(input, kernel, strides=self._strides, padding=self._padding)

        if bias:
            net = tf.nn.bias_add(net, bias)

        return net


class BiasLayerConstant(ILayer):
    """ Fixed, constant bias added to a layer """
    def __init__(self, bias):
        super().__init__()
        self._bias = bias

    def get_bias(self):
        return self._bias

    def __call__(self, input):
        return tf.nn.bias_add(input, self._bias)


class FullyConnectedLayer(ILayer):
    def __init__(self, shape, use_bias=True):
        super().__init__()
        self._shape = shape
        self._use_bias = use_bias

    def get_shape(self):
        return self._shape

    def using_bias(self):
        return self._use_bias

    def __call__(self, input, kernel, bias=None):
        # net = tf.linalg.matmul(input, kernel)
        net = tf.tensordot(input, kernel, axes=[1, 0])

        if bias:
            net = tf.nn.bias_add(net, bias)

        return net


# Alias name
Dense = FullyConnectedLayer


class PoolingLayer(ILayer):
    def __init__(self, pool_size=(2, 2)):
        """ In this case shape is the receptive field size to average over """
        px = pool_size[0]
        py = pool_size[1]
        self._ksize = [1, px, py, 1]
        self._strides = [1, px, py, 1]

    def get_ksize(self):
        return self._ksize

    def get_strides(self):
        return self._strides


class AveragePoolingLayer(PoolingLayer):
    def __init__(self, pool_size):
        super().__init__(pool_size)

    def __call__(self, input):
        return tf.nn.avg_pool(input, ksize=super(AveragePoolingLayer, self).get_ksize(),
                              strides=super(AveragePoolingLayer, self).get_strides(), padding="SAME")


class MaxPoolingLayer(PoolingLayer):
    def __init__(self, pool_size):
        super().__init__(pool_size)

    def __call__(self, input):
        return tf.nn.max_pool(input, ksize=super(MaxPoolingLayer, self).get_ksize(),
                              strides=super(MaxPoolingLayer, self).get_strides(), padding="SAME")


class GlobalAveragePooling:
    """ Pool over entire spatial dimensions"""
    def __init__(self):
        super().__init__()

    def __call__(self, input, keep_dims=True):
        return tf.reduce_mean(input, [1, 2], keep_dims=keep_dims, name='global_pool')


class DropoutLayer(ILayer):
    def __init__(self, keep_prob):
        super().__init__()
        self._keep_prob = keep_prob

    def __call__(self, input):
        return tf.nn.dropout(input, self._keep_prob)


class BatchNormalisationLayer(ILayer):
    def __init__(self, num_features, affine=True, variance_epsilon=0.001, beta_initializer=tf.zeros_initializer(),
                 gamma_initializer=tf.ones_initializer(), moving_mean_initializer=tf.zeros_initializer(),
                 moving_variance_initializer=tf.ones_initializer()):

        """ If affine is False, the scale and offset parameters won't be used
            When affine=False the output of BatchNorm is equivalent to considering gamma=1 and beta=0 as constants. """
        super().__init__()
        self._num_features = num_features
        self._affine = affine
        self._variance_epsilon = variance_epsilon

        self.beta_initializer = beta_initializer
        self.gamma_initializer = gamma_initializer
        self.moving_mean_initializer = moving_mean_initializer
        self.moving_variance_initializer = moving_variance_initializer

    def is_affine(self):
        return self._affine

    def get_num_features(self):
        return self._num_features

    def get_variance_epsilon(self):
        return self._variance_epsilon

    def __call__(self, input, mean, variance, offset, scale):
        return tf.nn.batch_normalization(input, mean, variance, offset, scale, variance_epsilon=self._variance_epsilon)


class ReLU(ILayer):
    def __init__(self):
        super().__init__()

    def __call__(self, input):
        return tf.nn.relu(input)


class ReLU6(ILayer):
    def __init__(self):
        super().__init__()

    def __call__(self, input):
        return tf.nn.relu6(input)


class hswish(ILayer):
    def __init__(self):
        super().__init__()

    def __call__(self, x):
        return x * tf.nn.relu6(x + 3) / 6


class SoftMax(ILayer):
    def __init__(self):
        super().__init__()

    def __call__(self, input):
        return tf.nn.softmax(input)


class Flatten(ILayer):
    def __init__(self):
        super().__init__()

    def __call__(self, input):
        return tf.layers.flatten(input)


""" Multilayer classes e.g. residual layers etc """


class MobileNetV2BottleNeck(ILayer):
    def __init__(self, k, t, c, strides=(1, 1)):
        """
        See: https://towardsdatascience.com/review-mobilenetv2-light-weight-model-image-classification-8febb490e61c

        :param k: Number of input channels
        :param t: Expansion factor
        :param c: Number of output channels
        :param strides: Depthwise stride
        """
        super().__init__()

        px = strides[0]
        py = strides[1]
        self._strides = [1, px, py, 1]
        self._k = k
        self._t = t
        self._c = c

        super().__init__()

    def __call__(self, input, expansion_kernel, expansion_bias, depthwise_kernel, depthwise_bias,
                 projection_kernel, projection_bias):

        # Just use tf.layers ...
        # expansion_mean, expansion_variance, expansion_scale, expansion_offset,
        # depthwise_mean, depthwise_variance, depthwise_scale, depthwise_offset,
        # projection_mean, projection_variance, projection_scale, projection_offset):

        # Expansion layer
        net = tf.nn.conv2d(input, expansion_kernel, strides=[1, 1, 1, 1], padding="SAME")
        net = tf.nn.bias_add(net, expansion_bias)
        net = tf.layers.batch_normalization(net)
        net = tf.nn.relu6(net)

        # Depthwise layer
        net = tf.nn.depthwise_conv2d(net, depthwise_kernel, strides=self._strides, padding="SAME")
        net = tf.nn.bias_add(net, depthwise_bias)
        net = tf.layers.batch_normalization(net)
        net = tf.nn.relu6(net)

        # Projection layer (linear)
        net = tf.nn.conv2d(net, projection_kernel, strides=[1, 1, 1, 1], padding="SAME")
        net = tf.nn.bias_add(net, projection_bias)
        net = tf.layers.batch_normalization(net)

        # Residual add only if stride=1 and depths match
        # See: https://github.com/tensorflow/models/blob/415e8a450f289bcbc8c665d7a68cf36e12101155/research/slim/nets/mobilenet/conv_blocks.py#L315
        if self._strides == [1, 1, 1, 1] and net.get_shape().as_list()[3] == input.get_shape().as_list()[3]:
            return net + input
        else:
            return net

    def get_k(self):
        return self._k

    def get_t(self):
        return self._t

    def get_c(self):
        return self._c

    def get_strides(self):
        return self._strides
