// Create a text parameter named DataFolder, pointing to this project's powerbi/data.
// Create function LoadData from this block:
(name as text) as table =>
let
    Source = Csv.Document(File.Contents(DataFolder & "/" & name & ".csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    NumericNames = {"order_id","order_item_id","product_id","customer_id","category_id",
        "department_id","geo_key","shipping_mode_key","quantity","year","month","quarter",
        "weekday","observed_days","days_in_month","partial_month","is_comparable",
        "is_canceled","is_over_schedule","is_order_conflict","item_count","source_row",
        "orders","order_items","planned_days_min","planned_days_max"},
    RealNames = {"sales","gross_sales","reported_profit","discount","discount_rate",
        "unit_price","actual_days","planned_days","positive_over_days"},
    Conversions = List.Transform(Table.ColumnNames(Headers), (c) =>
        {c, if List.Contains(NumericNames,c) then Int64.Type
            else if List.Contains(RealNames,c) then type number
            else if c="date_key" or c="date" then type date
            else if c="order_date" or c="shipping_date" then type datetime
            else type text}),
    EmptyToNull = Table.ReplaceValue(Headers,"",null,Replacer.ReplaceValue,Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(EmptyToNull,Conversions,"en-US")
in Typed

// Create eight separate queries; the following are individual expressions:
// fact_orders      = LoadData("fact_orders")
// fact_order_items = LoadData("fact_order_items")
// dim_product      = LoadData("dim_product")
// dim_customer     = LoadData("dim_customer")
// dim_date         = LoadData("dim_date")
// dim_geography    = LoadData("dim_geography")
// dim_shipping     = LoadData("dim_shipping")
// build_metadata   = LoadData("build_metadata")

