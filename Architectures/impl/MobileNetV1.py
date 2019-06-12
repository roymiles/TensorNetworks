from Architectures.architectures import IArchitecture
from Layers.impl.core import *


class MobileNetV1(IArchitecture):
    """ This is the original MobileNet architecture for ImageNet
        Of course, the convolutional layers are replaced with depthwise separable layers """

    def DepthSepConv(self, shape, stride, depth):
        # Depth is pretty much shape[3] (if included)
        w = shape[0]
        h = shape[1]
        c = shape[2]
        depth_multiplier = 1

        # By default, don't regularise depthwise filters
        sequential = [
            DepthwiseConvLayer(shape=[w, h, c, depth_multiplier], strides=(stride, stride), use_bias=False),
            BatchNormalisationLayer(num_features=c * depth_multiplier),
            ReLU(),
            # Pointwise
            ConvLayer(shape=[1, 1, c * depth_multiplier, depth], use_bias=False),
            # Not managed to integrate moving average decay
            BatchNormalisationLayer(num_features=depth),
            ReLU()
        ]

        return sequential

    def __init__(self, num_classes, channels):
        network = [
            # NOTE: Comments are for input size
            ConvLayer(shape=[3, 3, channels, 32], strides=(2, 2)),
            ReLU(),

            *self.DepthSepConv(shape=[3, 3, 32], stride=1, depth=64),
            *self.DepthSepConv(shape=[3, 3, 64], stride=2, depth=128),
            *self.DepthSepConv(shape=[3, 3, 128], stride=1, depth=128),
            *self.DepthSepConv(shape=[3, 3, 128], stride=2, depth=256),
            *self.DepthSepConv(shape=[3, 3, 256], stride=1, depth=256),
            *self.DepthSepConv(shape=[3, 3, 256], stride=2, depth=512),
            *self.DepthSepConv(shape=[3, 3, 512], stride=1, depth=512),
            *self.DepthSepConv(shape=[3, 3, 512], stride=1, depth=512),
            *self.DepthSepConv(shape=[3, 3, 512], stride=1, depth=512),
            *self.DepthSepConv(shape=[3, 3, 512], stride=1, depth=512),
            *self.DepthSepConv(shape=[3, 3, 512], stride=1, depth=512),
            *self.DepthSepConv(shape=[3, 3, 512], stride=2, depth=1024),
            *self.DepthSepConv(shape=[3, 3, 1024], stride=1, depth=1024),

            # ConvLayer(shape=[1, 1, 1024, 1024], use_bias=False),
            GlobalAveragePooling(keep_dims=False),
            FullyConnectedLayer(shape=[1024, num_classes])
        ]

        super().__init__(network)
