class Morph:
    """Time-based smoothstep, including seamless direction reversal."""
    def __init__(self,duration=.28):
        self.duration=duration
        self.start=0.0
        self.target=0.0
        self.began=0.0

    def value(self,now):
        t=max(0,min(1,(now-self.began)/self.duration))
        ease=t*t*(3-2*t)
        return self.start+(self.target-self.start)*ease

    def aim(self,target,now,duration=None):
        target=float(bool(target))
        if target!=self.target:
            self.start=self.value(now)
            self.target=target
            self.began=now
            if duration is not None:self.duration=duration
        return self.value(now)


class Spring:
    """Critically damped motion that preserves speed when hover reverses."""
    def __init__(self,duration=.28):
        self.position=0.0
        self.velocity=0.0
        self.target=0.0
        self.omega=8/duration
        self.last=None

    def value(self,now):
        import math
        if self.last is None:self.last=now
        dt=max(0,now-self.last)
        self.last=now
        offset=self.position-self.target
        coefficient=self.velocity+self.omega*offset
        decay=math.exp(-self.omega*dt)
        self.position=self.target+(offset+coefficient*dt)*decay
        self.velocity=(self.velocity-self.omega*coefficient*dt)*decay
        if abs(self.position-self.target)<.0003 and abs(self.velocity)<.02:
            self.position=self.target
            self.velocity=0
        return max(0,min(1,self.position))

    def aim(self,target,now,duration=None):
        value=self.value(now)
        self.target=float(bool(target))
        if duration:self.omega=8/duration
        return value
