from .a import StationA
import math


# Mixin allows for finer control over the mro
class StationAReloadMixin:
    @property
    def max_samples_per_set(self) -> int:
        return len(self._sources)
    
    @property
    def sets_of_samples(self) -> int:
        return math.ceil(self._num_samples/self.max_samples_per_set)
    
    @property
    def remaining_samples(self) -> int:
        return self._num_samples - self._done_samples 
    
    def transfer_samples(self):
        self._done_samples = 0
        refills = self.sets_of_samples - 1
        
        self.logger.info("using {} samples per time. Refills needed: {}.".format(self.max_samples_per_set, refills))
        for set_idx in reversed(range(self.sets_of_samples)):
            self.logger.debug("{} remaining samples".format(self.remaining_samples))
            for s, d in self.non_control_positions(self._sources[:self.remaining_samples], self._dests_single[self._done_samples:]):
                self.transfer_sample(s, d)
                self._done_samples += 1
            if set_idx:
                self.logger.info("Please refill {} samples".format(min(self.remaining_samples, self.max_samples_per_set)))
                self._ctx.pause()


# Subclass is more straightforward
class StationAReload(StationAReloadMixin, StationA):
    pass


# Copyright (c) 2020 Covmatic.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.