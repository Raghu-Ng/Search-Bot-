# Write the app code to a file
with open('patent_app.py', 'w') as f:
    f.write('''
import streamlit as st
import os
import requests
from serpapi import GoogleSearch
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
import json

# Page configuration
st.set_page_config(
    page_title="Patent Similarity Finder",
    page_icon="🔍",
    layout="wide"
)

# Add CSS for better styling
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .patent-box {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        border-left: 5px solid #4e8cff;
    }
    .feature-match {
        margin-top: 10px;
        padding-left: 20px;
    }
    .justification {
        font-size: 0.9em;
        color: #555;
        padding-left: 30px;
        border-left: 2px solid #ddd;
        margin-left: 10px;
    }
    .highlight {
        background-color: #ffff99;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions (same as in your original code)
def get_patent_results(query, api_key):
    try:
        search = GoogleSearch({
            "q": query + " site:patents.google.com",
            "location": "United States",
            "api_key": api_key
        })
        results = search.get_dict()
        return results.get("organic_results", [])
    except Exception as e:
        st.error(f"Error in API search: {str(e)}")
        return []

def scrape_patent_details(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract Abstract
        abstract_tag = soup.find("meta", {"name": "DC.description"})
        abstract = abstract_tag["content"] if abstract_tag else ""

        # Extract Full Description
        description_tag = soup.find("div", {"class": "description"})
        description = description_tag.text.strip() if description_tag else ""

        # Extract Claims
        claims_section = soup.find("section", {"itemprop": "claims"})
        claims = claims_section.text.strip() if claims_section else ""

        full_text = f"{abstract}\\n\\n{description}\\n\\n{claims}"  # Combine all sections
        return full_text if full_text.strip() else "No detailed description available."
    except Exception as e:
        return f"Error scraping patent details: {str(e)}"

def compare_features(features, patent_text, similarity_threshold):
    matches = {}
    for feature in features:
        score = fuzz.partial_ratio(feature.lower(), patent_text.lower())  # Compare text similarity
        if score > similarity_threshold:  # If similarity > threshold, consider it a match
            sentences = patent_text.split('. ')  # Split text into sentences
            relevant_sentences = [s for s in sentences if fuzz.partial_ratio(feature.lower(), s.lower()) > 50]
            # Ensure at least one justification is found
            if relevant_sentences:
                matches[feature] = {"score": score, "justification": relevant_sentences[:3]}  # Limit to 3 justifications
            else:
                matches[feature] = {"score": score, "justification": ["No exact sentence found, but feature is present in the patent text."]}
    return matches

def search_best_matching_patents(new_invention, features, api_key, similarity_threshold, min_feature_matches, max_patents):
    query = new_invention
    patents = get_patent_results(query, api_key)
    best_patents = []  # Store patents that match required features

    # Progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, patent in enumerate(patents[:max_patents]):
        status_text.text(f"Analyzing patent {i+1}/{min(len(patents), max_patents)}...")
        progress_bar.progress((i+1)/min(len(patents), max_patents))

        title = patent.get('title', 'Untitled Patent')
        link = patent.get('link', '')

        # Skip if link is missing
        if not link:
            continue

        patent_text = scrape_patent_details(link)
        matches = compare_features(features, patent_text, similarity_threshold)

        if len(matches) >= min_feature_matches:
            best_patents.append((title, link, matches))

    progress_bar.empty()
    status_text.empty()

    return best_patents

# Main application
st.title("🔍 Patent Similarity Finder")
st.subheader("Find patents that match your invention features")

# Sidebar for API key and configuration
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("Enter your SerpAPI Key", type="password")
    st.info("You need a SerpAPI key to use this application. Get one at [SerpAPI](https://serpapi.com/).")

    st.subheader("Search Parameters")
    similarity_threshold = st.slider("Similarity Threshold (%)", 30, 90, 40, 5)
    min_feature_matches = st.slider("Minimum Features to Match", 1, 10, 3, 1)
    max_patents = st.slider("Maximum Patents to Analyze", 5, 20, 10, 1)

# Input form
with st.form("patent_search_form"):
    new_invention = st.text_area("Describe your new invention", height=100,
                                placeholder="E.g., A SYSTEM AND METHOD FOR ORGANIZING A VIRTUAL INTERVIEW BACKGROUND")

    # Features input with example
    st.subheader("Enter Features (one per line)")
    features_text = st.text_area("Features", height=150,
                               placeholder="Virtual interview interface\\nAutomated interview report generation\\nCandidate preparation system")

    # Form submission button
    submit_button = st.form_submit_button("Search Patents")

# Process the search
if submit_button:
    if not api_key:
        st.error("Please enter your SerpAPI key in the sidebar.")
    elif not new_invention:
        st.error("Please describe your invention.")
    elif not features_text:
        st.error("Please enter at least one feature.")
    else:
        # Parse the features (one per line)
        features = [feature.strip() for feature in features_text.strip().split('\\n') if feature.strip()]

        if not features:
            st.error("Please enter valid features (one per line).")
        else:
            with st.spinner("Searching for matching patents..."):
                best_patents = search_best_matching_patents(
                    new_invention,
                    features,
                    api_key,
                    similarity_threshold,
                    min_feature_matches,
                    max_patents
                )

            # Display results
            st.header("Search Results")

            if not best_patents:
                st.warning("No patents found with enough feature matches. Try adjusting your search parameters.")
            else:
                st.success(f"Found {len(best_patents)} patents matching at least {min_feature_matches} features.")

                # Create tabs for each patent
                patent_tabs = st.tabs([f"Patent {i+1}: {title[:30]}..." for i, (title, _, _) in enumerate(best_patents)])

                for i, (patent_tab, (title, link, matches)) in enumerate(zip(patent_tabs, best_patents)):
                    with patent_tab:
                        st.markdown(f"### {title}")
                        st.markdown(f"[View Patent on Google Patents]({link})")

                        # Create a DataFrame to show feature matches
                        matches_data = []
                        for feature, data in matches.items():
                            matches_data.append({
                                "Feature": feature,
                                "Similarity Score": f"{data['score']}%"
                            })

                        # Display feature details
                        st.subheader("Matching Features")
                        for feature, data in matches.items():
                            st.markdown(f"""
                            <div class="feature-match">
                                <strong>{feature}</strong> (Similarity: {data['score']}%)
                                <div class="justification">
                                    {"<br>".join([f"• {sentence.strip()}" for sentence in data['justification']])}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                # Optional: Add a download button for the results
                result_json = json.dumps([{
                    "patent_title": title,
                    "patent_link": link,
                    "matches": matches
                } for title, link, matches in best_patents], indent=2)

                st.download_button(
                    label="Download Results as JSON",
                    data=result_json,
                    file_name="patent_matches.json",
                    mime="application/json"
                )

# Footer
st.markdown("---")
st.markdown("### How to use this tool")
with st.expander("See Instructions"):
    st.markdown("""
    1. Enter your SerpAPI key in the sidebar
    2. Describe your invention in the text area
    3. List the features of your invention (one per line)
    4. Click 'Search Patents' to find matching patents
    5. Adjust the parameters in the sidebar as needed:
       - Similarity Threshold: Minimum similarity score required (higher = stricter matching)
       - Minimum Features to Match: Number of features that must match for a patent to be included
       - Maximum Patents to Analyze: Maximum number of patents to search through
    """)

st.markdown("**Note:** This tool uses fuzzy matching to find relevant patents. The results are for research purposes only and do not constitute legal advice.")
''')