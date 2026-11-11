import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.plotting import PlotBuilder

def test_ticks_outside_view_not_reported_as_clipped(tmp_path):
    fig,ax=plt.subplots(figsize=(8.4,4.4))
    ax.plot([.05,.30],[50,345],label='Линия')
    ax.set_xlabel('WACC');ax.set_ylabel('USD');ax.margins(.03,.1)
    ax.set_xticks([0,.05,.1,.2,.3,.35]);ax.set_xlim(.04,.31)
    result=PlotBuilder(tmp_path).finish(fig,'test','Проверка','unit test')
    assert result['status']=='PASS'
