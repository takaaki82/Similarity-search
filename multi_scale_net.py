import chainer
import chainer.links as L
import chainer.functions as F
import numpy as np
from chainer.initializers import constant, uniform


class MultiscaleNet(chainer.Chain):

    def __init__(self, n_class, pretrained_model=None, mean=None, initialW=None, initialBias=None):
        self.n_class = n_class
        self.mean = mean
        self.initialbias = initialBias

        self.insize = 224

        if mean is None:
            # imagenet means
            self.mean = np.array([123.68, 116.779, 103.939], dtype=np.float32)[:, np.newaxis, np.newaxis]

        if initialW is None:
            # employ default initializers used in BVLC. For more detail, see
            self.initialW = uniform.LeCunUniform(scale=1.0)

        if pretrained_model:
            # As a sampling process is time-consuming
            # we employ a zero initializer for faster computation
            self.initialW = constant.Zero()

        super(MultiscaleNet, self).__init__()
        with self.init_scope():
            # Deep layers: GoogleNet of BatchNormalization version
            self.conv1 = L.Convolution2D(None, 64, 7, stride=2, pad=3)
            self.norm1 = L.BatchNormalization(64)
            self.conv2 = L.Convolution2D(None, 192, 3, stride=1, pad=1)
            self.norm2 = L.BatchNormalization(192)
            self.inc3a = L.InceptionBN(None, 64, 64, 64, 64, 96, "avg", 32)
            self.inc3b = L.InceptionBN(None, 64, 64, 96, 64, 96, "avg", 64)
            self.inc3c = L.InceptionBN(None, 0, 128, 160, 64, 96, "max", stride=2)
            self.inc4a = L.InceptionBN(None, 224, 64, 96, 96, 128, "avg", 128)
            self.inc4b = L.InceptionBN(None, 192, 96, 128, 96, 128, "avg", 128)
            self.inc4c = L.InceptionBN(None, 128, 128, 160, 128, 160, "avg", 128)
            self.inc4d = L.InceptionBN(None, 64, 128, 192, 160, 192, "avg", 128)
            self.inc4e = L.InceptionBN(None, 0, 128, 192, 192, 256, "max", stride=2)
            self.inc5a = L.InceptionBN(None, 352, 192, 320, 160, 224, "avg", 128)
            self.inc5b = L.InceptionBN(None, 352, 192, 320, 192, 224, "max", 128)
            self.loss3_fc = L.Linear(None, self.n_class, initialW=self.initialW)

            # Shallow layers
            self.conv_s1 = L.Convolution2D(None, 96, 3, stride=4, pad=1, initialW=0.02*np.sqrt(3*3*3))
            self.norm_s1 = L.BatchNormalization(96)
            self.conv_s2 = L.Convolution2D(None, 96, 3, stride=4, pad=1, initialW=0.02*np.sqrt(3*3*3))
            self.norm_s2 = L.BatchNormalization(96)

            # Final layers
            self.fc4_1 = L.Linear(None, 4096)
            self.fc4_2 = L.Linear(None, self.n_class)

    def __call__(self, x, t):
        # Deep layers
        h1 = F.max_pooling_2d(F.relu(self.norm1(self.conv1(x))), 3, stride=2, pad=1)
        h1 = F.max_pooling_2d(F.relu(self.norm2(self.conv2(h1))), 3, stride=2, pad=1)

        h1 = self.inc3a(h1)
        h1 = self.inc3b(h1)
        h1 = self.inc3c(h1)
        h1 = self.inc4a(h1)

        h1 = self.inc4b(h1)
        h1 = self.inc4c(h1)
        h1 = self.inc4d(h1)

        h1 = self.inc4e(h1)
        h1 = self.inc5a(h1)
        h1 = F.average_pooling_2d(self.inc5b(h1), 7)
        h1 = self.loss3_fc(h1)

        h1 = F.normalize(h1)

        # Shallow layers
        h2 = F.average_pooling_2d(x, 4, stride=4, pad=2)
        h2 = F.max_pooling_2d(F.relu(self.norm_s1(self.conv_s1(h2))), 5, stride=4, pad=1)
        h3 = F.average_pooling_2d(x, 8, stride=8, pad=4)
        h3 = F.max_pooling_2d(F.relu(self.norm_s2(self.conv_s2(h3))), 4, stride=2, pad=1)

        h23 = F.concat((h2, h3), axis=1)
        h23 = F.normalize(F.reshape(h23, (x.data.shape[0], 3072)))

        h = F.concat((h1, h23), axis=1)

        h = F.normalize(F.relu(self.fc4_1(h)))
        h = self.fc4_2(h)

        return h




