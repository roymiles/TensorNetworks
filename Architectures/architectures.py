class IArchitecture:
    """ All architecture must inherit from this class """
    def __init__(self, network):
        # Array of sequential layers
        self._network = network

    def num_layers(self):
        return len(self._network)

    def get_layer(self, layer_idx):
        return self._network[layer_idx]

    def get_network(self):
        return self._network
