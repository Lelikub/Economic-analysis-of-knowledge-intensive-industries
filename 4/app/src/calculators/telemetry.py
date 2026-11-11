from datetime import timedelta
from math import radians,sin,cos,atan2,sqrt
from ..models import Incident

EARTH_RADIUS_KM=6371.0088
GPS_MAX_SPEED_KMH=200.0  # контроль качества ж/д: заведомо консервативная граница

def haversine(lat1,lon1,lat2,lon2,radius=EARTH_RADIUS_KM):
    a,b=radians(lat1),radians(lat2)
    dlat=b-a; dlon=radians(lon2-lon1)
    h=sin(dlat/2)**2+cos(a)*cos(b)*sin(dlon/2)**2
    h=min(1,max(0,h))
    return radius*2*atan2(sqrt(h),sqrt(1-h))

class TelemetryCalculator:
    def calculate(self,data):
        samples=data.samples; interval=data.interval_minutes
        episodes=[]; group=[]; shocks=[]; norms=[]; segments=[]
        def close_group():
            if not group: return
            start,end=group[0],group[-1]
            episodes.append(Incident('REAL_INCIDENT_TEMPERATURE',start.index,end.index,start.timestamp.isoformat(' '),end.timestamp.isoformat(' '),
                       (end.timestamp+timedelta(minutes=interval)).isoformat(' '),len(group),len(group)*interval,
                       min(x.temp_celsius for x in group),max(x.temp_celsius for x in group)))
            group.clear()
        for n,s in enumerate(samples):
            if n and (s.timestamp-samples[n-1].timestamp).total_seconds()!=interval*60: close_group()
            if s.temp_celsius< -22 or s.temp_celsius> -18: group.append(s)
            else: close_group()
            axes={'X':s.accel_x_g,'Y':s.accel_y_g,'Z':s.accel_z_g}
            norm=sqrt(sum(v*v for v in axes.values())); norms.append(norm)
            hit=[k for k,v in axes.items() if abs(v)>2.5]
            if hit:
                shocks.append(Incident('REAL_INCIDENT_SHOCK',s.index,s.index,s.timestamp.isoformat(' '),s.timestamp.isoformat(' '),s.timestamp.isoformat(' '),
                                       1,0,min(axes.values()),max(abs(v) for v in axes.values()),','.join(hit)))
            if n:
                prev=samples[n-1]
                dist=haversine(prev.latitude,prev.longitude,s.latitude,s.longitude)
                hours=(s.timestamp-prev.timestamp).total_seconds()/3600
                if hours<=0: raise ValueError('Невозрастающее время GPS')
                speed=dist/hours
                segments.append(dict(from_index=prev.index,to_index=s.index,distance_km=dist,speed_kmh=speed,
                                     accepted=speed<=GPS_MAX_SPEED_KMH,status='PASS' if speed<=GPS_MAX_SPEED_KMH else 'DATA_ERROR_GPS_JUMP'))
        close_group()
        return dict(temperature_incidents=episodes,shock_incidents=shocks,
                    total_violation_minutes=sum(e.duration_minutes for e in episodes),scrap=any(e.duration_minutes>30 for e in episodes),
                    peak_axis_g=max(max(abs(s.accel_x_g),abs(s.accel_y_g),abs(s.accel_z_g)) for s in samples),
                    peak_norm_g=max(norms),norms=norms,segments=segments,
                    distance_km=sum(v['distance_km'] for v in segments if v['accepted']),
                    excluded_gps_segments=sum(not v['accepted'] for v in segments),
                    observed_span_hours=(samples[-1].timestamp-samples[0].timestamp).total_seconds()/3600,
                    covered_hours=len(samples)*interval/60)
