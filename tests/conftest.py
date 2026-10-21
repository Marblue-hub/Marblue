import pandas as pd
import pytest


@pytest.fixture
def raw_rows():
    def make(overrides=None):
        row = {
            "Order Id": "1", "Order Item Id": "10", "Order Customer Id": "7",
            "Customer Id": "7", "order date (DateOrders)": "1/1/2017 10:00",
            "shipping date (DateOrders)": "1/5/2017 10:00",
            "Shipping Mode": "Standard Class", "Delivery Status": "Late delivery",
            "Order Status": "COMPLETE", "Days for shipping (real)": "4",
            "Days for shipment (scheduled)": "3", "Late_delivery_risk": "1",
            "Sales": "100", "Order Item Total": "90", "Order Item Discount": "10",
            "Order Item Discount Rate": "0.1", "Order Profit Per Order": "9",
            "Benefit per order": "9", "Sales per customer": "90",
            "Order Item Profit Ratio": "0.1", "Order Item Quantity": "1",
            "Order Item Product Price": "100", "Product Card Id": "5",
            "Order Item Cardprod Id": "5", "Product Category Id": "2",
            "Category Id": "2", "Category Name": "Example", "Product Name": "Widget",
            "Department Id": "3", "Department Name": "Dept",
            "Market": "Europe", "Order Region": "Western Europe",
            "Order Country": "France", "Order State": "Example state",
            "Customer Segment": "Consumer",
        }
        row.update(overrides or {})
        return row
    return make

