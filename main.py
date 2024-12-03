from time import sleep
import dateparser
import requests
import sqlite3

import copy
from collections import defaultdict
from datetime import datetime
import heapq

TOTAL_ORDERS = []

ORDERS_ENDPOINT = "https://www.zomato.com/webroutes/user/orders"
ZOMATO_COOKIES = {
    "cid": "", # Paste your Zomato cid here
    "PHPSESSID": "", # Paste your PHPSESSID here
    "zat": "", # Paste your zat cookie here
}

COOKIE = "; ".join([f"{key}={value}" for key, value in ZOMATO_COOKIES.items()])


DATABASE_NAME = "zomato_orders.sqlite"
TABLE_NAME = "orders"

conn = sqlite3.connect(DATABASE_NAME)
conn.row_factory = sqlite3.Row

c = conn.cursor()
c.execute(
    """
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY,
        total_cost INTEGER,
        order_time INTEGER,
        restaurant_id INTEGER,
        restaurant_name TEXT,
        establishment TEXTgit chec
    );
    """
)


def get_orders(page: int):
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'cookie': COOKIE,
        'dnt': '1',
        'pragma': 'no-cache',
        'referer': 'https://www.zomato.com/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
    }

    params = (
        ('page', page),
    )

    response = requests.get(ORDERS_ENDPOINT, headers=headers, params=params).json()
    orders = []

    if len(response["entities"]["ORDER"]) > 0:
        for order in response["entities"]["ORDER"].values():
            #VJ print(order["orderId"], order["totalCost"], order["orderDate"], order["resInfo"]["name"] )
            try:
                #VJ normalized_cost = int(order["totalCost"].replace("\u20b9", "").replace("₹", "").replace(".", "").replace(",", "") )
                normalized_cost = float(order["totalCost"].replace("₹", "").replace(",", ""))
                parsed_time = dateparser.parse(order["orderDate"])
            except Exception as e:
                print(e)
                continue

            orders.append({
                "order_id": order["orderId"],
                "total_cost": normalized_cost,
                "order_time": parsed_time.timestamp(),
                "restaurant_id": order["resInfo"]["id"],
                "restaurant_name": order["resInfo"]["name"],
                "establishment": order["resInfo"]["establishment"][0] if len(order["resInfo"]["establishment"]) > 0  else ""
            })

    return orders


def insert_orders(orders):
    for order in orders:
        c.execute(
            f"""
            INSERT INTO {TABLE_NAME} (
                order_id,
                total_cost,
                order_time,
                restaurant_id,
                restaurant_name,
                establishment
            )
            VALUES (
                :order_id,
                :total_cost,
                :order_time,
                :restaurant_id,
                :restaurant_name,
                :establishment
            )
            ON CONFLICT (order_id) DO UPDATE SET
                total_cost = :total_cost,
                order_time = :order_time,
                restaurant_id = :restaurant_id,
                restaurant_name = :restaurant_name,
                establishment = :establishment
            """,
            order
        )

    conn.commit()

# Function to find total money spent
def total_money_spent(orders):
    return sum(order['total_cost'] for order in orders)

# Function to find the top 3 restaurants by money spent
def top_3_restaurants(orders):
    restaurant_spending = defaultdict(float)
    for order in orders:
        restaurant_spending[order['restaurant_name']] += order['total_cost']
    
    # Get the top 3 restaurants by amount spent
    top_restaurants = heapq.nlargest(3, restaurant_spending.items(), key=lambda x: x[1])
    return top_restaurants

# Function to calculate total money spent by month in 'YYYY-Mon' format with restaurant aggregation
def total_spent_per_month(orders):
    monthly_spending = defaultdict(lambda: defaultdict(float))
    
    for order in orders:
        # Convert the timestamp to a datetime object
        order_date = datetime.fromtimestamp(order['order_time'])
        month = order_date.strftime('%Y-%b')  # Format as 'YYYY-Mon' (e.g., '2024-Jan')
        
        # Add the order cost to the respective month and restaurant
        monthly_spending[month][order['restaurant_name']] += order['total_cost']
    
    # Convert defaultdict to regular dict
    monthly_spending_dict = {month: dict(spends) for month, spends in monthly_spending.items()}
    
    sorted_months = sorted(monthly_spending_dict.items(), key=lambda x: sum(x[1].values()), reverse=True)
    return sorted_months


def get_all_orders():
    page = 1
    while True:
        orders = get_orders(page)
        if len(orders) == 0:
            break
        TOTAL_ORDERS.extend(copy.deepcopy(orders))
        insert_orders(orders)
        print(f"\rProcessed page: {page}", end="", flush=True)
        page += 1
        sleep(1/1000)


get_all_orders()

total_spent = total_money_spent(TOTAL_ORDERS)
print("\n--------------------------------------------------------------")
print(f"Total money spent: {total_spent:.2f}\n")

top_restaurants = top_3_restaurants(TOTAL_ORDERS)
print("Top 3 restaurants based on money spent:")
for restaurant, amount in top_restaurants:
    print(f"{restaurant}: {amount:.2f}")

print("--------------------------------------------------------------")

# Sorted monthly spending by total money spent
monthly_spending_sorted = total_spent_per_month(TOTAL_ORDERS)
for month, spends in monthly_spending_sorted:
    total_month_spent = sum(spends.values())
    print(f"\n{month}: {total_month_spent:.2f}")
    for restaurant, amount in spends.items():
        print(f"  {restaurant}: {amount:.2f}")

print("\n--------------------------------------------------------------")

