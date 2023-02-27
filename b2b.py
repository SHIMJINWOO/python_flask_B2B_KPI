import os 
from flask import Flask, render_template, request, session, redirect, url_for
import pandas as pd
import numpy as np
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.join('staticFiles', 'uploads')
ALLOWED_EXTENSIONS = {'csv'}
app = Flask(__name__, template_folder='templateFiles', static_folder='staticFiles')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'This is your secret key to utilize session in Flask'

@app.route('/')
def index():
    return render_template('index_upload_and_show_data.html')
@app.route('/',  methods=("POST", "GET"))
def uploadFile():
    if request.method == 'POST':
        # upload file flask
        uploaded_df = request.files['uploaded-file']
        # Extracting uploaded data file name
        data_filename = secure_filename(uploaded_df.filename)
        # flask upload file to database (defined uploaded folder in static path)
        uploaded_df.save(os.path.join(app.config['UPLOAD_FOLDER'], data_filename))
 
        # Storing uploaded file path in flask session
        session['uploaded_data_file_path'] = os.path.join(app.config['UPLOAD_FOLDER'], data_filename)
 
        return render_template('index_upload_and_show_data_page2.html')

@app.route('/show_data')
def showData():
    # Retrieving uploaded file path from session
    data_file_path = session.get('uploaded_data_file_path', None)
    # read csv file in python flask (reading uploaded csv file from uploaded server location)
    global uploaded_df
    uploaded_df = pd.read_csv(data_file_path, parse_dates=(['배차시각','픽업시각','완료시각','접수시각']))
    dateColumns = ['접수시각', '배차시각', '완료시각', '픽업시각']
    # 24시 초과하는 경우 +1일
    def plus1day(dateColumn):
        uploaded_df[dateColumn] = pd.to_datetime(uploaded_df[dateColumn])
        midnight_mask = uploaded_df['접수시각'].dt.hour == 0
        apply_mask = (~midnight_mask) | (uploaded_df[dateColumn].dt.hour != 0)
        uploaded_df[dateColumn] = np.where(apply_mask, uploaded_df[dateColumn] + pd.Timedelta(days=1), uploaded_df[dateColumn])
        uploaded_df[dateColumn] = uploaded_df[dateColumn] + pd.Timedelta(days=1) * (
            (uploaded_df[dateColumn].dt.hour == 0) & (dateColumn != '접수시각')
            | ((uploaded_df['접수시각'].dt.hour == 23) & (uploaded_df[dateColumn].dt.hour < 12) & (dateColumn == '픽업시각'))
        )
    for dateColumn in dateColumns:
        plus1day(dateColumn)


    #1.Store Arr추출 : stores
    storeArr = uploaded_df["매장명"].drop_duplicates()
    stores = storeArr.values

    #2.쓸데없는 열 삭제
    uploaded_df.drop(uploaded_df.columns[range(14,38)],axis=1,inplace=True)
    uploaded_df.drop(uploaded_df.columns[range(16,20)],axis=1,inplace=True)

    #3.접수-완료	접수-배차	배차-픽업	픽업-완료 추가 / 
    uploaded_df['접수-완료'] = (uploaded_df['완료시각'] - uploaded_df['접수시각'])
    uploaded_df['접수-배차'] = (uploaded_df['배차시각'] - uploaded_df['접수시각'])
    uploaded_df['배차-픽업'] = (uploaded_df['픽업시각'] - uploaded_df['배차시각'])
    uploaded_df['픽업-완료'] = (uploaded_df['완료시각'] - uploaded_df['픽업시각'])
    uploaded_df['접수-픽업'] = (uploaded_df['픽업시각'] - uploaded_df['접수시각'])

    calulated_dateColumns = ['접수-완료', '접수-배차', '배차-픽업', '픽업-완료']
    def modify_timedelta(td):
        if td.days == 1:
            return pd.Timedelta(0)
        else:
            return td

    # Apply the function to all Timedelta objects in the DataFrame
    uploaded_df = uploaded_df.applymap(lambda x: modify_timedelta(x) if isinstance(x, pd.Timedelta) else x)

    def convertDatetime(dateColumn):
        uploaded_df[dateColumn] = pd.to_datetime(uploaded_df[dateColumn]).dt.strftime("%H:%M:%S")
    def removeDayData(calulated_dateColumn):
        uploaded_df[calulated_dateColumn] = uploaded_df[calulated_dateColumn].astype(str).map(lambda x: x[7:])

    #5. 매장 별 데이터 분리 (DataFrame)
    for i in range(0,len(stores)):
        globals()['store'+str(i)] = uploaded_df.loc[uploaded_df['매장명']== stores[i]]
        globals()['store'+str(i)].reset_index(inplace=True,drop=True)

    #6. 브랜드 별 퀄리티 지표 만들기
    storeTotalCall = []
    storeBrand = []
    storeCancelCall = []
    storeCancelRatio = []
    under20minutestoPickup = []
    under20minutesRatio = []
    under40minutestoComplete = [] 
    under40minutestoRatio = []
    manuallyAddCall = [] 

    #접수-완료 평균
    # 시간 평균 (접수시간 = 배차시간인 과적+배차 건수 시간 계산은 제외, 개수나 금액에는 포함
    storeAvg_1=[]
    storeAvg_2=[]
    storeAvg_3=[]
    storeAvg_4=[]
    for i in range(0,len(stores)):
        storeTotalCall.append(len(uploaded_df[(uploaded_df['매장명']== stores[i])]))
        storeBrand.append(uploaded_df[(uploaded_df['매장명']== stores[i])]["브랜드"].drop_duplicates().values)
        storeCancelCall.append(len(uploaded_df[(uploaded_df['매장명']== stores[i]) & (uploaded_df['상태']== 'CANCELED')]))
        under20minutestoPickup.append(len(uploaded_df[(uploaded_df['매장명']== stores[i]) & (uploaded_df['상태']== 'COMPLETED') &(uploaded_df['접수-픽업'] < pd.Timedelta(minutes=20))]))
        under40minutestoComplete.append(len(uploaded_df[(uploaded_df['매장명']== stores[i]) & (uploaded_df['상태']== 'COMPLETED') &(uploaded_df['접수-완료'] < pd.Timedelta(minutes=40))]))
        manuallyAddCall.append(len(uploaded_df[(uploaded_df['매장명']== stores[i]) & (uploaded_df['상태']== 'COMPLETED') &(uploaded_df['픽업-완료'] == pd.Timedelta(minutes=0, seconds=0))]))
        storeAvg_1.append(uploaded_df[(uploaded_df['매장명']== stores[i]) & (uploaded_df['상태']== 'COMPLETED') & (uploaded_df['접수-완료']!= pd.Timedelta(minutes=0, seconds=0))]['접수-완료'].mean())
        storeAvg_2.append(uploaded_df[(uploaded_df['매장명']== stores[i]) & (uploaded_df['상태']== 'COMPLETED') & (uploaded_df['접수-배차']!= pd.Timedelta(minutes=0, seconds=0))]['접수-배차'].mean())
        storeAvg_3.append(uploaded_df[(uploaded_df['매장명']== stores[i]) & (uploaded_df['상태']== 'COMPLETED') & (uploaded_df['배차-픽업']!= pd.Timedelta(minutes=0, seconds=0))]['배차-픽업'].mean())
        storeAvg_4.append(uploaded_df[(uploaded_df['매장명']== stores[i]) & (uploaded_df['상태']== 'COMPLETED') & (uploaded_df['픽업-완료']!= pd.Timedelta(minutes=0, seconds=0))]['픽업-완료'].mean())

    for i in range(0,len(storeTotalCall)):
        storeCancelRatio.append( str(round((storeCancelCall[i]/(storeTotalCall[i]-manuallyAddCall[i]))*100,2))+"%" )
        under20minutesRatio.append (str(round(((under20minutestoPickup[i]-manuallyAddCall[i])/(storeTotalCall[i]-manuallyAddCall[i]))*100,2))+"%" )
        under40minutestoRatio.append (str(round(((under40minutestoComplete[i]-manuallyAddCall[i])/(storeTotalCall[i]-manuallyAddCall[i]))*100,2))+"%" )
    storeAvgs = [storeAvg_1, storeAvg_2, storeAvg_3, storeAvg_4]
    def change_nat_to_timedelta(storeAvg):
        for i, val in enumerate(storeAvg):
            if pd.isnull(val):
                storeAvg[i] = pd.Timedelta(seconds=0)
        return storeAvg
    for storeAvg in storeAvgs:
        change_nat_to_timedelta(storeAvg)
    
    rounded_list = [str(pd.Timedelta(seconds=int(mean_timedelta.total_seconds() // 1)))[7:] for mean_timedelta in storeAvg_1]
    rounded_list2 = [str(pd.Timedelta(seconds=int(mean_timedelta.total_seconds() // 1)))[7:] for mean_timedelta in storeAvg_2]
    rounded_list3 = [str(pd.Timedelta(seconds=int(mean_timedelta.total_seconds() // 1)))[7:] for mean_timedelta in storeAvg_3]
    rounded_list4 = [str(pd.Timedelta(seconds=int(mean_timedelta.total_seconds() // 1)))[7:] for mean_timedelta in storeAvg_4]
    df_storeQuality = pd.DataFrame([stores,storeTotalCall,storeCancelCall,storeCancelRatio,rounded_list,rounded_list2,rounded_list3,rounded_list4,under20minutesRatio,under40minutestoRatio,storeBrand]).transpose()

    for dateColumn in dateColumns:
        convertDatetime(dateColumn)
    for calulated_dateColumn in calulated_dateColumns:
        removeDayData(calulated_dateColumn)
    df_storeQuality.rename(columns={
        0:'상점명',1:'전체건수',2:'취소건수',3:'취소율',4:'접수->완료 평균',5:'접수->배차 평균',6:'배차->픽업 평균',7:'픽업->완료 평균', 8:'20분 내 픽업율',9:'40분 내 완료율',10:'브랜드'}, inplace=True)
    df_버거킹 = df_storeQuality.loc[df_storeQuality['브랜드'] == '버거킹']
    df_버거킹.reset_index(inplace=True,drop=True)
    df_배스킨라빈스 = df_storeQuality.loc[df_storeQuality['브랜드'] == '배스킨라빈스(SPC)']
    df_배스킨라빈스.reset_index(inplace=True,drop=True)
    df_던킨도너츠 = df_storeQuality.loc[df_storeQuality['브랜드'] == '던킨도너츠(SPC)']
    df_던킨도너츠.reset_index(inplace=True,drop=True)
    df_파스쿠찌 = df_storeQuality.loc[df_storeQuality['브랜드'] == '파스쿠찌(SPC)']
    df_파스쿠찌.reset_index(inplace=True,drop=True)
    df_파리바게뜨 = df_storeQuality.loc[df_storeQuality['브랜드'] == '파리바게뜨(SPC)']
    df_파리바게뜨.reset_index(inplace=True,drop=True)
    df_이마트 = df_storeQuality.loc[df_storeQuality['브랜드'] == '이마트24']
    df_이마트.reset_index(inplace=True,drop=True)
    df_해피버틀러 = df_storeQuality.loc[df_storeQuality['브랜드'] == '해피버틀러(SPC)']
    df_해피버틀러.reset_index(inplace=True,drop=True)
    df_버거킹_raw = uploaded_df.loc[uploaded_df['브랜드'] == '버거킹']
    df_버거킹_raw.reset_index(inplace=True,drop=True)
    df_배스킨라빈스_raw = uploaded_df.loc[uploaded_df['브랜드'] == '배스킨라빈스(SPC)']
    df_배스킨라빈스_raw.reset_index(inplace=True,drop=True)
    df_던킨도너츠_raw = uploaded_df.loc[uploaded_df['브랜드'] == '던킨도너츠(SPC)']
    df_던킨도너츠_raw.reset_index(inplace=True,drop=True)
    df_파스쿠찌_raw = uploaded_df.loc[uploaded_df['브랜드'] == '파스쿠찌(SPC)']
    df_파스쿠찌_raw.reset_index(inplace=True,drop=True)
    df_파리바게뜨_raw = uploaded_df.loc[uploaded_df['브랜드'] == '파리바게뜨(SPC)']
    df_파리바게뜨_raw.reset_index(inplace=True,drop=True)
    df_이마트_raw = uploaded_df.loc[uploaded_df['브랜드'] == '이마트24']
    df_이마트_raw.reset_index(inplace=True,drop=True)
    df_해피버틀러_raw = uploaded_df.loc[uploaded_df['브랜드'] == '해피버틀러(SPC)']
    df_해피버틀러_raw.reset_index(inplace=True,drop=True)
    #uploaded_df_csv = pd.DataFrame(uploaded_df)
    # pandas dataframe to html table flask
    table_total = df_storeQuality.to_html(index=False)
    table_bk = df_버거킹.to_html(index=False)
    table_br = df_배스킨라빈스.to_html(index=False)
    table_dk = df_던킨도너츠.to_html(index=False)
    table_pc = df_파스쿠찌.to_html(index=False)
    table_pb = df_파리바게뜨.to_html(index=False)
    table_em = df_이마트.to_html(index=False)
    table_hb = df_해피버틀러.to_html(index=False)
    table_total_raw = uploaded_df

    # convert the '접수시각' column to a datetime format
    uploaded_df['접수시각'] = pd.to_datetime(uploaded_df['접수시각'])
    # group by '브랜드' and calculate daily order counts for each brand
    daily_order_count = uploaded_df.groupby(['브랜드', '배달접수일자', uploaded_df['접수시각'].dt.floor('Min').dt.time])\
        .size().reset_index(name='num_times')
    daily_order_count = daily_order_count.groupby(['브랜드', '배달접수일자', 'num_times'])\
        ['num_times'].count().reset_index(name='count_of_counts')
    daily_order_count = daily_order_count.pivot_table(index=['브랜드', '배달접수일자'], columns='num_times',
                                                    values='count_of_counts', fill_value=0)
    daily_order_count.reset_index(inplace=True)
    daily_order_count = daily_order_count.to_html(index=False)
    
    
    return render_template('show_csv_data.html',
     table_total = table_total,
     table_bk=table_bk,
     table_br=table_br,
     table_dk=table_dk,
     table_pc=table_pc,
     table_pb=table_pb,
     table_em=table_em,
     table_hb=table_hb,
     table_total_raw =table_total_raw,
     daily_order_count=daily_order_count
     )

@app.route('/fairing_data')
def fairing_data():
    # Get the fairing data and pass it to the template
    global uploaded_df
    date_columns = ['접수시각', '배차시각', '완료시각', '픽업시각']

    # 24시 초과하는 경우 +1일
    def plus1day(date_column):
        uploaded_df[date_column] = pd.to_datetime(uploaded_df[date_column])
        midnight_mask = uploaded_df['접수시각'].dt.hour == 0
        apply_mask = (~midnight_mask) | (uploaded_df[date_column].dt.hour != 0)
        uploaded_df[date_column] = np.where(apply_mask, uploaded_df[date_column] + pd.Timedelta(days=1), uploaded_df[date_column])
        uploaded_df[date_column] = uploaded_df[date_column] + pd.Timedelta(days=1) * (
            (uploaded_df[date_column].dt.hour == 0) & (date_column != '접수시각')
            | ((uploaded_df['접수시각'].dt.hour == 23) & (uploaded_df[date_column].dt.hour < 12) & (date_column == '픽업시각'))
        )

    for date_column in date_columns:
        plus1day(date_column)

    # 1. Store Arr 추출: stores
    store_arr = uploaded_df["매장명"].drop_duplicates()
    stores = store_arr.values

    # 2. 쓸데없는 열 삭제
    uploaded_df.drop(uploaded_df.columns[range(14, 38)], axis=1, inplace=True)
    uploaded_df.drop(uploaded_df.columns[range(16, 20)], axis=1, inplace=True)

    # convert the '접수시각' column to a datetime format
    uploaded_df['접수시각'] = pd.to_datetime(uploaded_df['접수시각'])

    # group by '브랜드' and calculate daily order counts for each brand
    daily_order_count = uploaded_df.groupby(['브랜드', '배달접수일자', uploaded_df['접수시각'].dt.floor('Min').dt.time])\
        .size().reset_index(name='num_times')
    daily_order_count = daily_order_count.groupby(['브랜드', '배달접수일자', 'num_times'])\
        ['num_times'].count().reset_index(name='count_of_counts')
    daily_order_count = daily_order_count.pivot_table(index=['브랜드', '배달접수일자'], columns='num_times',
                                                    values='count_of_counts', fill_value=0)
    daily_order_count.reset_index(inplace=True)

    return render_template('fairing_data.html', daily_order_count=daily_order_count)




if __name__=='__main__':
    app.run(debug = True)