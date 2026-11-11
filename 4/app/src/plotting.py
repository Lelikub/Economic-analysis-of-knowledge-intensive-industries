from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from .serialization import write_json
from .presentation import hub_label

COLORS=['#2176ae','#29947a','#df9140']
LABELS={'Air_Express':'Авиация','Rail_Express':'Железная дорога','Sea_Road_Multimodal':'Море + автомобиль'}

class PlotBuilder:
    def __init__(self,output):
        self.output=Path(output); self.folder=self.output/'figures'; self.folder.mkdir(parents=True,exist_ok=True)
        self.metadata=[]
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,'axes.labelsize':10,'legend.fontsize':9,'axes.spines.top':False,'axes.spines.right':False})

    def read(self,name): return pd.read_csv(self.output/'tables'/(name+'.csv'))

    def finish(self,fig,key,title,source):
        n=len(self.metadata)+1
        fig.suptitle(f'Рисунок {n}. {title}',fontsize=12,y=.98)
        fig.text(.02,.015,'Источник: '+source+'; расчётная учебная модель',fontsize=7,color='#555555')
        fig.tight_layout(rect=(.01,.055,.99,.92))
        fig.canvas.draw()
        renderer=fig.canvas.get_renderer(); w,h=fig.canvas.get_width_height()
        elements=[]; series=[]
        for ax in fig.axes:
            if not ax.get_xlabel() or not ax.get_ylabel(): raise ValueError(f'{key}: отсутствуют подписи осей')
            xticks=[tick.label1 for tick in ax.xaxis.get_major_ticks() if min(ax.get_xlim())<=tick.get_loc()<=max(ax.get_xlim())]
            yticks=[tick.label1 for tick in ax.yaxis.get_major_ticks() if min(ax.get_ylim())<=tick.get_loc()<=max(ax.get_ylim())]
            for label in [ax.xaxis.label,ax.yaxis.label,ax.title,*xticks,*yticks]:
                if not label.get_visible() or not label.get_text(): continue
                b=label.get_window_extent(renderer)
                inside=b.x0>=-2 and b.y0>=-2 and b.x1<=w+2 and b.y1<=h+2
                elements.append(dict(text=label.get_text(),inside=inside))
                if not inside: raise ValueError(f'{key}: подпись вне рисунка: {label.get_text()}')
            legend=ax.get_legend()
            if legend:
                b=legend.get_window_extent(renderer)
                if b.x0<0 or b.y0<0 or b.x1>w or b.y1>h: raise ValueError(f'{key}: легенда обрезана')
            for line in ax.lines:
                xy=line.get_xydata()
                if not np.isfinite(xy).all(): raise ValueError(f'{key}: NaN/inf в серии')
                xlim=ax.get_xlim(); ylim=ax.get_ylim()
                if len(xy) and (xy[:,0].min()<min(xlim)-1e-6 or xy[:,0].max()>max(xlim)+1e-6 or xy[:,1].min()<min(ylim)-1e-6 or xy[:,1].max()>max(ylim)+1e-6):
                    # axhline/axvline используют координаты осей для одной компоненты.
                    if line.get_transform()==ax.transData: raise ValueError(f'{key}: данные обрезаны осями')
                series.append(dict(label=line.get_label(),points=len(xy),min_y=float(xy[:,1].min()),max_y=float(xy[:,1].max())))
            for patch in ax.patches:
                vals=[patch.get_x(),patch.get_y(),patch.get_width(),patch.get_height()] if hasattr(patch,'get_height') else []
                if vals and not np.isfinite(vals).all(): raise ValueError(f'{key}: NaN в столбцах')
        path=self.folder/(key+'.png');fig.savefig(path,dpi=200,facecolor='white')
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im: dimensions=list(im.size)
        entry=dict(number=n,key=key,title=title,source=source,path=str(path.resolve()),dimensions=dimensions,series=series,labels=elements,status='PASS')
        self.metadata.append(entry);plt.close(fig)
        return entry

    def build(self):
        base=self.read('tco_baseline'); names=list(base.route_id)
        fig,ax=plt.subplots(figsize=(8.4,4.7));bottom=np.zeros(len(base))
        components=[('freight_usd','Фрахт'),('insurance_usd','Страхование'),('inventory_usd','Капитал в пути'),('packaging_usd','Упаковка'),('risk_usd','Риск'),('border_usd','CBAM')]
        for (col,label),color in zip(components,['#2176ae','#669bbc','#70b89c','#df9140','#bd5d61','#7d6caf']):
            values=base[col].to_numpy()/1000; ax.bar(range(len(base)),values,bottom=bottom,label=label,color=color);bottom+=values
        for i,v in enumerate(bottom): ax.text(i,v+3,f'{v:.2f}',ha='center',fontsize=10)
        ax.set_xticks(range(len(base)),[LABELS[k] for k in names]);ax.set_xlabel('Маршрут');ax.set_ylabel('Логистические затраты, тысяч долларов\nна партию 20 тонн')
        ax.set_ylim(0,bottom.max()*1.14);ax.legend(ncol=3,loc='upper center',bbox_to_anchor=(.5,-.16));ax.grid(axis='y',alpha=.2)
        self.finish(fig,'01_tco','Структура логистических затрат','module1_tco_cbam_input.json → tco_baseline.csv')
        for key,xlabel,scale,title in [('wacc','Средневзвешенная стоимость капитала, % годовых',100,'Чувствительность к стоимости капитала'),('cargo_value','Цена груза, тысяч долларов за тонну',.001,'Чувствительность к стоимости груза'),('lead_time','Общий срок моря и автомобильной доставки, суток',1,'Изменение только времени морского плеча')]:
            df=self.read(key);fig,ax=plt.subplots(figsize=(8.4,4.4))
            for name,color in zip(names,COLORS): ax.plot(df[key]*scale,df[name]/1000,label=LABELS[name],color=color,lw=2)
            ax.set_xlabel(xlabel);ax.set_ylabel('Логистические затраты, тысяч долларов\nна партию 20 тонн');ax.legend();ax.grid(alpha=.25);ax.margins(.03,.10)
            roots=self.read('break_even')
            subset=roots[(roots.parameter==('price_usd_per_t' if key=='cargo_value' else 'sea_total_days')) & (roots.status=='CROSSING') & (roots.wacc==.15)] if key!='wacc' else pd.DataFrame()
            for _,root in subset.iterrows():
                x=root['value'];xx=x*scale
                yy=float(np.interp(x,df[key],df[root['a']]))/1000
                ax.scatter([xx],[yy],color='#a43d43',zorder=5)
                ax.annotate(f'{xx:.2f}; {yy:.2f}',(xx,yy),xytext=(8,12),textcoords='offset points',fontsize=8)
            self.finish(fig,{'wacc':'02_wacc','cargo_value':'03_price','lead_time':'04_lead'}[key],title,'module1_tco_cbam_input.json → '+key+'.csv')
        df=self.read('ets');fig,ax=plt.subplots(figsize=(8.4,4.4))
        for (p,group),color in zip(df.groupby('price_usd_per_t'),COLORS):
            ax.plot(group.ets_eur_tco2,group.air_minus_rail_usd/1000,label=f'Цена {p/1000:g} тысяч долларов за тонну',color=color,lw=2)
        ax.set_xlabel('Цена европейской квоты, евро за тонну углекислого газа');ax.set_ylabel('Затраты авиации минус железной дороги,\nтысяч долларов');ax.legend();ax.grid(alpha=.2)
        self.finish(fig,'05_ets','Авиация и железная дорога: стоимость капитала 15%','module1_tco_cbam_input.json → ets.csv')
        for key in ['multi','single']:
            df=self.read('flows_'+key).set_index('facility_id');fig,ax=plt.subplots(figsize=(8.4,4.4))
            im=ax.imshow(df.to_numpy(),cmap='Blues',vmin=0,vmax=450,aspect='auto')
            ax.set_xticks(range(len(df.columns)),df.columns);ax.set_yticks(range(len(df.index)),[hub_label(j) for j in df.index])
            for j,row in enumerate(df.to_numpy()):
                for i,v in enumerate(row): ax.text(i,j,f'{v:g}',ha='center',va='center',color='white' if v>280 else '#222222')
            ax.set_xlabel('Номер потребителя');ax.set_ylabel('Распределительный хаб');cb=fig.colorbar(im,ax=ax);cb.set_label('Поток, тонн в год')
            # colorbar не имеет двух предметных осей; проверяется через подпись шкалы.
            cb.ax.set_xlabel(' ')
            self.finish(fig,'06_multi' if key=='multi' else '07_single','Снабжение '+('из нескольких источников' if key=='multi' else 'из одного источника'),'module2_cflp_*.csv → flows_'+key+'.csv')
        df=self.read('facilities_multi');fig,ax=plt.subplots(figsize=(8.4,4.4));x=np.arange(len(df))
        ax.bar(x-.18,df.capacity_tons,width=.36,label='Физическая мощность',color='#b8c6d4');ax.bar(x+.18,df.load_tons,width=.36,label='Оптимальная загрузка',color='#29947a')
        ax.set_xticks(x,[hub_label(j).replace(' — ','\n') for j in df.facility_id]);ax.set_xlabel('Распределительный хаб');ax.set_ylabel('Тонн в год');ax.legend();ax.grid(axis='y',alpha=.2)
        self.finish(fig,'08_capacity','Резерв мощностей оптимальной сети','module2_cflp_*.csv → facilities_multi.csv')
        df=self.read('cflp_comparison').set_index('model');fig,axes=plt.subplots(1,2,figsize=(8.4,4.4))
        vals=[df.loc['multi','lp_gap_pct'],df.loc['bigm_milp','lp_gap_pct']]
        axes[0].bar(['Реальные мощности','Завышенные мощности'],vals,color=['#29947a','#bd5d61']);axes[0].set_xlabel('Постановка');axes[0].set_ylabel('Разрыв линейной релаксации, %');axes[0].tick_params(axis='x',labelsize=8)
        for i,v in enumerate(vals): axes[0].text(i,v+1,f'{v:.2f}%',ha='center')
        axes[0].set_ylim(0,max(vals)*1.18)
        keys=['multi','physical_lp','bigm_milp','bigm_lp'];x=np.arange(4)
        axes[1].bar(x,[df.loc[k,'median_seconds']*1000 for k in keys],color='#2176ae');axes[1].set_xticks(x,['K:\nцелочисленная','K:\nлинейная','M:\nцелочисленная','M:\nлинейная'],rotation=25,fontsize=8)
        axes[1].set_xlabel('Медиана трёх запусков CBC');axes[1].set_ylabel('Стеночное время, мс')
        self.finish(fig,'09_bigm','Big-M: разрыв релаксации и время','module2_cflp_*.csv → cflp_comparison.csv')
        df=self.read('telemetry');df['hour']=(pd.to_datetime(df.timestamp)-pd.to_datetime(df.timestamp.iloc[0])).dt.total_seconds()/3600
        fig,ax=plt.subplots(figsize=(8.4,4.4));ax.plot(df.hour,df.temp_celsius,color='#2176ae',lw=.8,label='Температура')
        ax.axhspan(-22,-18,color='#29947a',alpha=.12,label='Допустимый диапазон');ax.axhline(-18,color='#bd5d61',ls='--');ax.axhline(-22,color='#bd5d61',ls='--')
        episodes=self.read('temperature_incidents')
        for _,e in episodes.iterrows():
            x=df.loc[df['index']==e.start_index,'hour'].iloc[0];end=x+e.duration_minutes/60
            ax.axvspan(x,end,color='#bd5d61',alpha=.25)
            ax.annotate(f'{e.duration_minutes:g} мин; максимум {e.maximum:g} °C',(x,e.maximum),xytext=(15,5),textcoords='offset points',fontsize=8)
        ax.set_xlabel('Часы от 10.04.2026 08:00');ax.set_ylabel('Температура, °C');ax.set_ylim(-22.6,-15);ax.legend(loc='lower right');ax.grid(alpha=.2)
        self.finish(fig,'10_temperature','Холодовая цепь: непрерывное нарушение','module3_iot_telemetry.csv → telemetry.csv, temperature_incidents.csv')
        fig,ax=plt.subplots(figsize=(8.4,4.4))
        for col,label in [('accel_x_g','Ось X'),('accel_y_g','Ось Y'),('accel_z_g','Ось Z'),('a_total_g','Векторная норма')]: ax.plot(df.hour,df[col],label=label,lw=.7,alpha=.8)
        ax.axhline(2.5,color='#bd5d61',ls='--',label='Осевой порог 2.5g')
        shock=self.read('shock_incidents')
        for _,e in shock.iterrows():
            row=df.loc[df['index']==e.start_index].iloc[0]
            ax.annotate(f'Индекс {int(e.start_index)}: Z={e.maximum:g}g\nНорма={row.a_total_g:.4f}g',(row.hour,row.a_total_g),xytext=(-60,15),textcoords='offset points',fontsize=8)
        ax.set_xlabel('Часы от 10.04.2026 08:00');ax.set_ylabel('Ускорение, g');ax.set_ylim(-.7,3.8);ax.legend(ncol=3,loc='lower center');ax.grid(alpha=.2)
        self.finish(fig,'11_shock','Трёхосевой акселерометр и удар','module3_iot_telemetry.csv → telemetry.csv, shock_incidents.csv')
        seg=self.read('gps_segments');fig,axes=plt.subplots(1,2,figsize=(8.4,4.4))
        axes[0].plot(df.longitude,df.latitude,lw=1,color='#2176ae',label='Измеренные GPS-точки');axes[0].scatter([df.longitude.iloc[0],df.longitude.iloc[-1]],[df.latitude.iloc[0],df.latitude.iloc[-1]],color=['#29947a','#bd5d61'])
        axes[0].set_xlabel('Долгота, градусы');axes[0].set_ylabel('Широта, градусы');axes[0].legend(fontsize=7)
        axes[1].plot(seg.to_index,seg.cumulative_accepted_km,color='#29947a');axes[1].set_xlabel('Индекс отсчёта');axes[1].set_ylabel('Накопленный GPS-путь, км')
        self.finish(fig,'12_gps','Контрольный участок телеметрии','module3_iot_telemetry.csv → gps_segments.csv')
        write_json(self.output/'plot_validation.json',self.metadata)
        return self.metadata
