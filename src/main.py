print("# ------------ 1.0 Setting up Spark")
from collections import defaultdict
from timeit import default_timer as timer

import pyspark
from pyspark.sql import SparkSession
from pyspark import SparkConf
import pyspark.sql.functions as f

conf=SparkConf()
conf.set("spark.executor.memory", "2G")
conf.set("spark.executor.instances", "4")

spark = SparkSession.builder \
                    .appName('ludek-cizinsky-assgn-02') \
                    .config(conf=conf) \
                    .getOrCreate()

print("Done!\n")

# ---------------------- 3.1 Specific DataFrame Queries implementation
def q1(bs):
    """
    Analyze business.json to find the total number of reviews for all businesses.
    The output should be in the form of a Spark DataFrame with one value representing the count.
    """

    return bs.agg({'review_count': 'sum'})

def q2(bs):
    """
    Analyze business.json to find all businesses that have received 5 stars and that have
    been reviewed by 1000 or more users. The output should be in the form of DataFrame of
    (name, stars, review count) 
    """

    return bs.filter((bs.stars == 5) & (bs.review_count >= 1000)).select("name", "stars", "review_count")

def q3(us):
    """
    Analyze user.json to find the influencers who have written more than 1000 reviews. The
    output should be in the form of DataFrame of user id.
    """
    
    return us.filter(us.review_count > 1000).select("user_id")


def q4(bs, rs, a3):
    """
    Analyze review.json, business.json, and a view created from your answer to Q3 to
    find the businesses that have been reviewed by more than 5 influencer users.
    """

    # Join business, reviews and corresponding influencers using inner join
    bs_rs = bs.join(rs, "business_id").join(a3, "user_id")

    # For each business, count number of unique influencers
    bs_inf_count = bs_rs.groupby("business_id").agg(f.countDistinct("user_id").alias("countd"))

    
    return bs_inf_count.filter(bs_inf_count.countd > 5).select("business_id")

def q5(rs, us):
    """
    Analyze review.json and user.json to find an ordered list of users based on the average star counts they have given in all their reviews.
    """
    
    rs_us = rs.join(us, "user_id").groupby("user_id").mean("stars").sort("avg(stars)", ascending=False)

    return rs_us


# ---------------------- 3.2 Authenticity Study

# ----------------- EDA

def eda(bs, rs):
    """
    What is the percentage of reviews containing a variant of the word "authentic"?
    How many reviews contain the string "legitimate" grouped by restaurant categories?
    How many reviews contain the string "legitimate" grouped by businesses type (type of cuisine)?
    Is there a difference in the amount of authenticity language used in the different areas? (e.g., by state, north/south, urban/rural)
    """

    # ---- What is the percentage of reviews containing a variant of the word "authentic"?
    # Get reviews for only restaurants
    rest = bs[bs.categories.contains('Restaurants')]
    rest_rs = rest.join(rs, "business_id")

    # Get reviews with a form of the word authentic
    rest_rs_auth = rest_rs.filter(rest_rs.text.rlike('authentic'))

    # Get the percentage of such revirews
    auth_perc = (rest_rs_auth.count()/rest_rs.count())*100
    print(f">> Percentage of reviews with a form of authentic: {auth_perc} %\n")

    # ---- How many reviews contain the string "legitimate" grouped by restaurant categories/businesses type (type of cuisine)?
    # Get reviews with word legitimate
    rest_rs_legit = rest_rs.filter(rest_rs.text.rlike('legitimate'))

    # Get count of categories from ALL reviews
    cat_count_all = rest_rs.withColumn('category', f.explode(f.split(f.col('categories'), ', '))).groupBy('category').agg({"category": "count"}).withColumnRenamed("count(category)", "count_all")

    # Get count of categories from reviews which include word legitimate
    cat_count_legit = rest_rs_legit.withColumn('category', f.explode(f.split(f.col('categories'), ', '))).groupBy('category').agg({"category": "count"}).withColumnRenamed("count(category)", "count_legit")

    # Normalize by the count in the actual category
    cat_count_legit_all = cat_count_legit.join(cat_count_all, "category")
    cat_count_legit_all = cat_count_legit_all.withColumn("normalized", cat_count_legit_all.count_legit/cat_count_legit_all.count_all)

    # Show sorted according to the count legit
    print(">> Count of the categories of reviews which include word 'legit':")
    cat_count_legit_all.sort("count_legit", ascending=False).toPandas().to_csv('data/category_count.csv')
    print("See the result in 'data/category_count.csv'.\n")

    # ---- Is there a difference in the amount of authenticity language used in the different areas?
    print(">> Count of the reviews, which are using authenticity lang, per state and per city:")
    rest_rs = rest_rs.withColumn("isThereAuth", rest_rs.text.rlike('(legitimate)|(authentic)'))
    rest_rs_cube = rest_rs.cube("state", "city", "isThereAuth").count().orderBy("count", ascending=False)
    rest_rs_cube.toPandas().to_csv('data/location_count.csv')
    print("See the result in 'data/location_count.csv'.\n")

    return rest_rs

# ----------------- Hypothesis testing

def ht(rest_rs):

    # Add column mentioning whether the review includes some NEGATIVE words
    rest_rs = rest_rs.withColumn("isThereNeg", rest_rs.text.rlike('(dirty)|(cheap)|(rude)'))

    # Add column mentioning whether the review includes some POSITIVE words
    rest_rs = rest_rs.withColumn("isTherePos", rest_rs.text.rlike('(nice)|(fresh)|(eleg)'))

    # Get reviews with authentic language and negative/positive language
    rest_rs_neg = rest_rs.filter((rest_rs.isThereAuth) & (rest_rs.isThereNeg))
    rest_rs_pos = rest_rs.filter((rest_rs.isThereAuth) & (rest_rs.isTherePos))

    # Look at the categories
    # * All
    cat_count_all = rest_rs.withColumn('category', f.explode(f.split(f.col('categories'), ', '))).groupBy('category').agg({"category": "count"}).withColumnRenamed("count(category)", "count_all")

    # * Negative
    rest_rs_neg_count = rest_rs_neg.withColumn('category', f.explode(f.split(f.col('categories'), ', '))).groupBy('category').agg({"category": "count"}).withColumnRenamed("count(category)", "c_neg")
    rest_rs_neg_count = rest_rs_neg_count.join(cat_count_all, "category")
    rest_rs_neg_count = rest_rs_neg_count.withColumn("normalized", (rest_rs_neg_count.c_neg/rest_rs_neg_count.count_all)*100)

    # * Positive
    rest_rs_pos_count = rest_rs_pos.withColumn('category', f.explode(f.split(f.col('categories'), ', '))).groupBy('category').agg({"category": "count"}).withColumnRenamed("count(category)", "c_pos")
    rest_rs_pos_count = rest_rs_pos_count.join(cat_count_all, "category")
    rest_rs_pos_count = rest_rs_pos_count.withColumn("normalized", (rest_rs_pos_count.c_pos/rest_rs_pos_count.count_all)*100)

    # Save the results
    print(">> Show the cuisines with the highest relative frequency of negative authentic reviews:")
    rest_rs_neg_count.orderBy("normalized", ascending=False).toPandas().to_csv('data/ht_neg_cat_count.csv')
    print(f"See the results in 'data/ht_neg_cat_count.csv'.\n")

    print(">> Show the cuisines with the highest relative frequency of positive authentic reviews:")
    rest_rs_pos_count.orderBy("normalized", ascending=False).toPandas().to_csv('data/ht_pos_cat_count.csv')
    print(f"See the results in 'data/ht_pos_cat_count.csv'.\n")


def main():

    print("# ------------ 2.0 Loading data from json files")
    start = timer() 
    bs = spark.read.json("/datasets/yelp/business.json")
    rs = spark.read.json("/datasets/yelp/review.json")
    us = spark.read.json("/datasets/yelp/user.json")
    total = round(timer() - start, 2)
    print(f"> Loading json data done. ({total} s)\n")

    print("# ------------ 3.1 Specific DataFrame Queries") 
    start = timer()
    a1 = q1(bs)
    a2 = q2(bs)
    a3 = q3(us)
    a4 = q4(bs, rs, a3)
    a5 = q5(rs, us)
    total = round(timer() - start, 2)
    print(f"> Building queries done. ({total} s)\n")

    print("# ------------ 3.2 Authenticity Study")
    print("# ------- 3.2.1 Data exploration")
    start = timer() 
    rest_rs = eda(bs, rs)
    total = round(timer() - start, 2)
    print(f"> Data exploration done. ({total} s)\n")


    print("# ------- 3.2.1 Hypothesis testing")
    start = timer()
    ht(rest_rs)
    total = round(timer() - start, 2)
    print(f"> Hypothesis testing done. ({total} s)\n")

    print("# ------------ 3.3 Loading data in the parquet format")
    start = timer()
    bspq = spark.read.parquet("/datasets/yelp/parquet/business.parquet")
    rspq = spark.read.parquet("/datasets/yelp/parquet/review.parquet")
    uspq = spark.read.parquet("/datasets/yelp/parquet/user.parquet")
    total = round(timer() - start, 2)
    print(f"> Loading parquet data done. ({total} s)\n") 

if __name__ == "__main__":
    main()

