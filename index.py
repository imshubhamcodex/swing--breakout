import datetime
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from colorama import init, Fore, Back, Style
from invoker import (
    prepare_data,
    login_with_enctoken,
    get_instruments_list,
    get_historical_dataset
)
from utilities import findIToken
from logger import printing
print = printing

# Initialize colorama
init()

def calculate_ema(df, length=5):
    df['ema'] = df['close'].ewm(span=length, adjust=False).mean()
    return df

def detect_swing(df, test_candle, marked_candle, swing_threshold=20): 
    # Get the subset of the dataframe between the two candles
    subset_df = df.loc[test_candle:marked_candle]
    
    # Check if there is a significant price movement upwards or downwards
    swing = subset_df['high'].max() - subset_df['low'].min()
    return swing > swing_threshold


def check_upper_wick(df, threshold=4, window=4):
    test_candles = []
    marked_candles = []

    for index in range(len(df)):
        row = df.iloc[index]
        upper_wick = row['high'] - max(row['open'], row['close'])
        lower_wick = min(row['open'], row['close']) - row['low']
        if upper_wick > threshold:
            detected_marked_candle = False
            for j in range(index + 1, len(df)):
                if 0 < row['high'] - df.iloc[j]['high']  <= 1.5:
                    if j - index < window:
                        break
                    else: 
                        marked_candles.append(df.index[j])
                        detected_marked_candle = True
                        break
                else:
                    if row['high'] - df.iloc[j]['high'] < 0:
                        break
                    if row['high'] - df.iloc[j]['high']  > 1.5:
                        continue

            if detected_marked_candle:
                test_candles.append(df.index[index])

                if not detect_swing(df, test_candles[-1], marked_candles[-1], swing_threshold=35):
                    test_candles.pop()
                    marked_candles.pop()

    return test_candles, marked_candles

def check_lower_wick(df, threshold=4, window=4):
    test_candles = []
    marked_candles = []

    for index in range(len(df)):
        row = df.iloc[index]
        upper_wick = row['high'] - max(row['open'], row['close'])
        lower_wick = min(row['open'], row['close']) - row['low']
        if lower_wick > threshold:
            detected_marked_candle = False
            for j in range(index + 1, len(df)):
                if 0 < df.iloc[j]['low'] - row['low'] <= 1.5:
                    if j - index < window:
                        break
                    else: 
                        marked_candles.append(df.index[j])
                        detected_marked_candle = True
                        break
                else:
                    if df.iloc[j]['low'] - row['low'] < 0:
                        break
                    if df.iloc[j]['low'] - row['low'] > 1.5:
                        continue

            if detected_marked_candle:
                test_candles.append(df.index[index])
                
                if not detect_swing(df, test_candles[-1], marked_candles[-1], swing_threshold=35):
                    test_candles.pop()
                    marked_candles.pop()

    return test_candles, marked_candles


def find_trigger_candle_up(df, test_candles, marked_candles, window=4):
    # Convert lists of datetime to pandas Timestamps
    test_candles = [pd.Timestamp(ts) for ts in test_candles]
    marked_candles = [pd.Timestamp(ts) for ts in marked_candles]

    # Initialize a list to store trigger candles
    trigger_candles = []

    for test_candle_date in test_candles:
        test_candle_high = df.loc[test_candle_date, 'high']
        
        for marked_candle_date in marked_candles:
            # Check if marked_candle_date is after the test_candle_date
            if marked_candle_date > test_candle_date:
                # Find the first candle after the marked_candle_date
                subsequent_df = df[df.index > marked_candle_date]
                # Iterate over the subsequent candles to find if any breaks the test_candle high
                for i in range(len(subsequent_df)):
                    date = subsequent_df.index[i]
                    high = subsequent_df.iloc[i]['high']
                    if high > test_candle_high:
                        if i < window:
                            break
                        elif i > window and detect_swing(df, marked_candle_date, date, swing_threshold=25):
                            trigger_candles.append(date)
                            break
                        else:
                            break
                    else:
                        continue
                break


    return trigger_candles


def find_trigger_candle_down(df, test_candles, marked_candles, window=4):
    # Convert lists of datetime to pandas Timestamps
    test_candles = [pd.Timestamp(ts) for ts in test_candles]
    marked_candles = [pd.Timestamp(ts) for ts in marked_candles]

    # Initialize a list to store trigger candles
    trigger_candles = []

    for test_candle_date in test_candles:
        test_candle_low = df.loc[test_candle_date, 'low']
        
        for marked_candle_date in marked_candles:
            # Check if marked_candle_date is after the test_candle_date
            if marked_candle_date > test_candle_date:
                # Find the first candle after the marked_candle_date
                subsequent_df = df[df.index > marked_candle_date]
                # Iterate over the subsequent candles to find if any breaks the test_candle high
                for i in range(len(subsequent_df)):
                    date = subsequent_df.index[i]
                    low = subsequent_df.iloc[i]['low']
                    if low < test_candle_low:
                        if i < window:
                            break
                        elif i > window and detect_swing(df, marked_candle_date, date, swing_threshold=25):
                            trigger_candles.append(date)
                            break
                        else:
                            break
                    else:
                        continue
                break
                

    return trigger_candles



def plot_data(df, test_candles, marked_candles, trigger_candles, type):
    # Calculate EMA
    df = calculate_ema(df, length=5)

    # Convert lists of datetime to pandas Timestamps
    test_candles = [pd.Timestamp(ts) for ts in test_candles]
    marked_candles = [pd.Timestamp(ts) for ts in marked_candles]
    trigger_candles = [pd.Timestamp(ts) for ts in trigger_candles]

    # Ensure that test_candles and marked_candles are in df index
    test_candles = [ts for ts in test_candles if ts in df.index]
    marked_candles = [ts for ts in marked_candles if ts in df.index]
    trigger_candles = [ts for ts in trigger_candles if ts in df.index]

    # Get the highs for the candles
    test_candles_highs = [df.loc[date, 'high'] for date in test_candles]
    marked_candles_highs = [df.loc[date, 'high'] for date in marked_candles]
    trigger_candles_highs = [df.loc[date, 'high'] for date in trigger_candles]

    # Create a Plotly figure
    fig = go.Figure()

    # Add Candlestick trace
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Candlestick',
        increasing_line_color='green',
        decreasing_line_color='red',
        increasing_fillcolor='green',
        decreasing_fillcolor='red'
    ))

    # Add EMA trace
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['ema'],
        mode='lines',
        name='EMA 5',
        line=dict(color='blue', width=1)
    ))

    # # Add scatter plot for test candles
    if test_candles:
        fig.add_trace(go.Scatter(
            x=test_candles,
            y=test_candles_highs,
            mode='markers',
            name='Test Candles',
            marker=dict(color='blue', symbol='triangle-up', size=10)
        ))

    # # Add scatter plot for marked candles
    if marked_candles:
        fig.add_trace(go.Scatter(
            x=marked_candles,
            y=marked_candles_highs,
            mode='markers',
            name='Marked Candles',
            marker=dict(color='black', symbol='circle', size=10)
        ))

    # # Add scatter plot for trigger candles
    if trigger_candles:
        fig.add_trace(go.Scatter(
            x=trigger_candles,
            y=trigger_candles_highs,
            mode='markers',
            name='Trigger Candles',
            marker=dict(color='orange' , symbol='diamond', size=10)
        ))

    # Update layout
    fig.update_layout(
        title='Trade:' + type,
        xaxis_title='Date',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        legend=dict(x=0, y=1.1, orientation='h')
    )

    # Show plot
    fig.show()

def main():
    # Login data fetch
    user_id, password, enctoken = prepare_data()

    # Trying login
    kite = login_with_enctoken(enctoken)

    print(Back.GREEN + "Hi", kite.profile()["user_shortname"],", successfully logged in." + Style.RESET_ALL)
    print(" ")

    # Fetching instruments list --> getting only FNO data instruments
    i_list = get_instruments_list(kite)

    timeframe = input("Enter Timeframe: ")
    ticker = input("Enter instrument name: ")
    iToken = findIToken(ticker, i_list)

    # iToken = "256265"  # nifty 50 
    # timeframe = "5"

    if not iToken:
        print("Invalid iToken")
        print("Exiting")
        return
    
    days = 7
    end_date = datetime.datetime.today()
    start_date = end_date - datetime.timedelta(days)
    delta_days = min(100, days)  # download date at once, in days
    interval = timeframe + "minute"

    print(f"\n{iToken} -- Downloading data...\n")
    historical_data = get_historical_dataset(kite, iToken, start_date, end_date, interval, delta_days)

    df = pd.DataFrame(historical_data)

    # Set 'date' as index
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)

    test_candles_up, marked_candles_up = check_upper_wick(df, threshold=4, window=4)
    test_candles_down, marked_candles_down = check_lower_wick(df, threshold=4, window=4)

    trigger_candles_up = find_trigger_candle_up(df, test_candles_up, marked_candles_up, window=4)
    trigger_candles_down = find_trigger_candle_down(df, test_candles_down, marked_candles_down, window=4)

    for date in trigger_candles_up:
        print("UP Trade:")
        print(" ", date)
    print("Total UP trade: ", len(trigger_candles_up))
    
    for date in trigger_candles_down:
        print("DOWN Trade:")
        print(" ", date)
    print("Total DOWN trade: ", len(trigger_candles_down))



    # test_candles = test_candles_up + test_candles_down
    # marked_candles = marked_candles_up + marked_candles_down
    # trigger_candles = trigger_candles_up + trigger_candles_down

    # Plot the data with EMA
    plot_data(df, test_candles_up, marked_candles_up, trigger_candles_up, type="UP")
    plot_data(df, test_candles_down, marked_candles_down, trigger_candles_down, type="DOWN")

if __name__ == "__main__":
    init()  # For colorama
    print(Back.RED)
    print("Designed by Shubham @https://github.com/imshubhamcodex/Kite")
    print(Style.RESET_ALL)
    main()
