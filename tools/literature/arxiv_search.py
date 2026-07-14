import pandas as pd
from arxiv import Search

# Define search query
query = "AI applied to bone classification"

# Search Arxiv
search = Search(query=query)

# Get results
results = search.results()

# Convert results to DataFrame
df = pd.DataFrame(results)

# Save results to CSV
df.to_csv("arxiv_results.csv", index=False)