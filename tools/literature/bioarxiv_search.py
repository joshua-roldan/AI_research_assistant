import pandas as pd
from bioarxiv import Search

# Define search query
query = "AI applied to bone classification"

# Search Bioarxiv
search = Search(query=query)

# Get results
results = search.results()

# Convert results to DataFrame
df = pd.DataFrame(results)

# Save results to CSV
df.to_csv("bioarxiv_results.csv", index=False)