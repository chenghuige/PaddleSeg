# Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import math
import os

import paddle
import paddle.nn as nn
import paddle.nn.functional as F
from paddle.nn import SyncBatchNorm as BatchNorm

from paddleseg.cvlibs import manager
from paddleseg import utils
from paddleseg.cvlibs import param_init
from paddleseg.utils import logger
from paddleseg.models.common import layer_libs, activation


@manager.MODELS.add_component
class FCN(nn.Layer):
    def __init__(self,
                 num_classes,
                 backbone,
                 pretrained=None,
                 backbone_indices=(-1, ),
                 channels=None):
        super(FCN, self).__init__()

        self.backbone = backbone
        backbone_channels = [
            backbone.feat_channels[i] for i in backbone_indices
        ]

        self.head = FCNHead(num_classes, backbone_indices, backbone_channels,
                            channels)
        utils.load_entire_model(self, pretrained)

    def forward(self, input):
        feat_list = self.backbone(input)
        logit_list = self.head(feat_list)
        return [
            F.resize_bilinear(logit, input.shape[2:]) for logit in logit_list
        ]


class FCNHead(nn.Layer):
    """
    A simple implementation for Fully Convolutional Networks for Semantic Segmentation.
    https://arxiv.org/abs/1411.4038

    Args:
        num_classes (int): the unique number of target classes.
        backbone (paddle.nn.Layer): backbone networks.
        model_pretrained (str): the path of pretrained model.
        backbone_indices (tuple): one values in the tuple indicte the indices of output of backbone.Default -1.
        backbone_channels (tuple): the same length with "backbone_indices". It indicates the channels of corresponding index.
        channels (int): channels after conv layer before the last one.
    """

    def __init__(self,
                 num_classes,
                 backbone_indices=(-1, ),
                 backbone_channels=(270, ),
                 channels=None):
        super(FCNHead, self).__init__()

        self.num_classes = num_classes
        self.backbone_indices = backbone_indices
        if channels is None:
            channels = backbone_channels[0]

        self.conv_1 = layer_libs.ConvBNReLU(
            in_channels=backbone_channels[0],
            out_channels=channels,
            kernel_size=1,
            padding='same',
            stride=1)
        self.cls = nn.Conv2d(
            in_channels=channels,
            out_channels=self.num_classes,
            kernel_size=1,
            stride=1,
            padding=0)
        self.init_weight()

    def forward(self, feat_list):
        logit_list = []
        x = feat_list[self.backbone_indices[0]]
        x = self.conv_1(x)
        logit = self.cls(x)
        logit_list.append(logit)
        return logit_list

    def init_weight(self):
        for layer in self.sublayers():
            if isinstance(layer, nn.Conv2d):
                param_init.normal_init(layer.weight, scale=0.001)
            elif isinstance(layer, (nn.BatchNorm, nn.SyncBatchNorm)):
                param_init.constant_init(layer.weight, value=1.0)
                param_init.constant_init(layer.bias, value=0.0)
