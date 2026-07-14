import pandas as pd
from biothings_client import PubmedClient

# Initialize Pubmed client
pubmed_client = PubmedClient()

# Define search query
query = "AI applied to bone classification"

# Search Pubmed
results = pubmed_client.query(query)

# Convert results to DataFrame
df = pd.DataFrame(results)

# Save results to CSV
df.to_csv("pubmed_results.csv", index=False)