import streamlit as st
import json
import os
from datetime import datetime
from src.api_clients import AlphaVantageClient, NewsAPIClient, YFinanceClient
from src.news_processor import NewsProcessor

# Page configuration
st.set_page_config(
    page_title="Stock News Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin: 10px 0;
    }
    .positive-sentiment {
        color: #10b981;
        font-weight: bold;
    }
    .negative-sentiment {
        color: #ef4444;
        font-weight: bold;
    }
    .neutral-sentiment {
        color: #6b7280;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)


def load_config():
    """Load configuration from stocks.json"""
    config_path = "config/stocks.json"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {}


def save_config(config):
    """Save configuration to stocks.json"""
    with open("config/stocks.json", "w") as f:
        json.dump(config, f, indent=2)


def initialize_session_state():
    """Initialize Streamlit session state"""
    if "config" not in st.session_state:
        st.session_state.config = load_config()
    if "news_cache" not in st.session_state:
        st.session_state.news_cache = {}
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = None


def get_api_clients(config):
    """Initialize API clients"""
    clients = {}

    # Alpha Vantage
    if config.get("apis", {}).get("alpha_vantage", {}).get("api_key") != "YOUR_ALPHA_VANTAGE_API_KEY":
        clients["alpha_vantage"] = AlphaVantageClient(
            config["apis"]["alpha_vantage"]["api_key"]
        )

    # NewsAPI
    if config.get("apis", {}).get("newsapi", {}).get("api_key") != "YOUR_NEWSAPI_API_KEY":
        clients["newsapi"] = NewsAPIClient(
            config["apis"]["newsapi"]["api_key"]
        )

    # YFinance (always available)
    clients["yfinance"] = YFinanceClient()

    return clients


def fetch_news(stocks, clients, keywords):
    """Fetch news from all available sources"""
    all_news = []
    processor = NewsProcessor()

    # Fetch from Alpha Vantage
    if "alpha_vantage" in clients:
        try:
            with st.spinner("Fetching from Alpha Vantage..."):
                av_news = clients["alpha_vantage"].get_news_sentiment(stocks, limit=50)
                all_news.extend(av_news)
        except Exception as e:
            st.warning(f"Alpha Vantage error: {e}")

    # Fetch from NewsAPI
    if "newsapi" in clients:
        try:
            with st.spinner("Fetching from NewsAPI..."):
                newsapi_articles = clients["newsapi"].search_news(
                    keywords=keywords,
                    days_back=7
                )
                all_news.extend(newsapi_articles)
        except Exception as e:
            st.warning(f"NewsAPI error: {e}")

    # Deduplicate
    unique_news = processor.deduplicate_news(all_news)

    # Filter by keywords
    filtered_news = processor.filter_by_keywords(unique_news, keywords)

    # Enrich with sentiment
    enriched_news = processor.enrich_articles(filtered_news, stocks)

    # Sort by relevance
    sorted_news = processor.sort_by_relevance(enriched_news)

    return sorted_news


def display_article(article, index):
    """Display a single news article"""
    with st.container():
        col1, col2 = st.columns([3, 1])

        with col1:
            title = article.get("title", "No title")
            url = article.get("url", "#")
            st.markdown(f"**[{title}]({url})**")

            # Source and date
            source = article.get("source", {})
            if isinstance(source, dict):
                source_name = source.get("name", "Unknown")
            else:
                source_name = str(source)

            publish_date = article.get("publishedAt", "Unknown date")
            st.caption(f"📰 {source_name} • {publish_date}")

            # Description
            description = article.get("description", "")
            if description:
                st.write(description[:200] + "..." if len(description) > 200 else description)

        with col2:
            # Sentiment badge
            impact = article.get("impact", "Neutral")
            impact_score = article.get("impact_score", 0)

            if impact == "Positive":
                st.markdown(f'<p class="positive-sentiment">✅ {impact}</p>', unsafe_allow_html=True)
            elif impact == "Negative":
                st.markdown(f'<p class="negative-sentiment">⚠️ {impact}</p>', unsafe_allow_html=True)
            else:
                st.markdown(f'<p class="neutral-sentiment">ℹ️ {impact}</p>', unsafe_allow_html=True)

            st.metric("Confidence", f"{impact_score:.0%}")

        st.divider()


def main():
    """Main Streamlit app"""
    initialize_session_state()
    config = st.session_state.config

    # Header
    st.title("📈 Real-Time Stock News Tracker")
    st.markdown("Stay updated with news impacting your stocks: legislation, regulations, politics, and more.")

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Stock management
        st.subheader("Manage Stocks")
        current_stocks = config.get("stocks", [])
        stocks_input = st.text_area(
            "Stocks (comma-separated, one per line):",
            value="\n".join(current_stocks),
            height=150,
            help="E.g., WTC.ASX, CPB, EDR.ASX, WDS.ASX, AD8.ASX, AMCR"
        )

        # Parse stocks
        new_stocks = [s.strip().upper() for s in stocks_input.split("\n") if s.strip()]

        # API Keys
        st.subheader("API Keys")
        alpha_key = st.text_input(
            "Alpha Vantage API Key",
            value=config.get("apis", {}).get("alpha_vantage", {}).get("api_key", ""),
            type="password",
            help="Get from https://www.alphavantage.co/"
        )

        newsapi_key = st.text_input(
            "NewsAPI Key",
            value=config.get("apis", {}).get("newsapi", {}).get("api_key", ""),
            type="password",
            help="Get from https://newsapi.org/"
        )

        # Save configuration
        if st.button("💾 Save Configuration", use_container_width=True):
            config["stocks"] = new_stocks
            config["apis"]["alpha_vantage"]["api_key"] = alpha_key
            config["apis"]["newsapi"]["api_key"] = newsapi_key
            save_config(config)
            st.session_state.config = config
            st.success("Configuration saved!")

        st.divider()

        # Display last refresh time
        if st.session_state.last_refresh:
            st.caption(f"Last refresh: {st.session_state.last_refresh}")

    # Main content
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tracked Stocks", len(new_stocks))
    with col2:
        sources_available = sum([
            alpha_key != config.get("apis", {}).get("alpha_vantage", {}).get("api_key", "YOUR_ALPHA_VANTAGE_API_KEY"),
            newsapi_key != config.get("apis", {}).get("newsapi", {}).get("api_key", "YOUR_NEWSAPI_API_KEY"),
            1  # yfinance always available
        ])
        st.metric("Data Sources", sources_available)
    with col3:
        if st.button("🔄 Refresh News", use_container_width=True):
            st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
            st.rerun()

    st.divider()

    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        sentiment_filter = st.multiselect(
            "Filter by Sentiment:",
            ["Positive", "Negative", "Neutral"],
            default=["Positive", "Negative", "Neutral"]
        )
    with col2:
        sort_option = st.selectbox(
            "Sort by:",
            ["Relevance", "Latest", "Most Impactful"]
        )

    st.divider()

    # Check if API keys are configured
    if not new_stocks:
        st.warning("⚠️ Add stocks in the sidebar to get started!")
        return

    if alpha_key == config.get("apis", {}).get("alpha_vantage", {}).get("api_key", "YOUR_ALPHA_VANTAGE_API_KEY") and \
       newsapi_key == config.get("apis", {}).get("newsapi", {}).get("api_key", "YOUR_NEWSAPI_API_KEY"):
        st.warning("⚠️ Please add at least one API key in the sidebar to fetch news!")
        st.info("Get free API keys from:\n- [Alpha Vantage](https://www.alphavantage.co/support/#api-key)\n- [NewsAPI](https://newsapi.org/register)")
        return

    # Fetch and display news
    keywords = config.get("keywords", [])
    clients = get_api_clients(config)

    news = fetch_news(new_stocks, clients, keywords)

    if not news:
        st.info("No news found matching your criteria. Try refreshing or adjusting your filters.")
        return

    # Filter by sentiment
    filtered_news = [n for n in news if n.get("impact") in sentiment_filter]

    if not filtered_news:
        st.info("No news matches the selected sentiment filters.")
        return

    # Display statistics
    positive_count = sum(1 for n in filtered_news if n.get("impact") == "Positive")
    negative_count = sum(1 for n in filtered_news if n.get("impact") == "Negative")
    neutral_count = sum(1 for n in filtered_news if n.get("impact") == "Neutral")

    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    with stat_col1:
        st.metric("Total Articles", len(filtered_news))
    with stat_col2:
        st.metric("Positive", positive_count, delta_color="off")
    with stat_col3:
        st.metric("Negative", negative_count, delta_color="off")
    with stat_col4:
        st.metric("Neutral", neutral_count, delta_color="off")

    st.divider()

    # Display articles
    st.subheader("📰 Latest News")
    for idx, article in enumerate(filtered_news[:50]):  # Limit to 50 articles
        display_article(article, idx)


if __name__ == "__main__":
    main()
