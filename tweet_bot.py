import os
import tweepy
import json
import random
import schedule
import time
import threading
import sys
import logging
import socket
from datetime import datetime
from dotenv import load_dotenv
# Import keep-alive module
import keep_alive
from openai import OpenAI

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Debug mode flag
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

def debug_log(message):
    """Log debug messages if DEBUG is enabled"""
    if DEBUG:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[DEBUG][{current_time}] {message}")

# Check if another instance is already running
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

# Only run if this is the first instance
if is_port_in_use(10000):
    print("Another instance of KOIYU is already running. Exiting.")
    sys.exit(0)

# Start the keep-alive server
keep_alive.run_keep_alive_server()

# Load environment variables
load_dotenv()

def check_required_env_vars():
    """Check that all required environment variables are present"""
    required_vars = [
        "TWITTER_API_KEY", 
        "TWITTER_API_SECRET", 
        "TWITTER_ACCESS_TOKEN", 
        "TWITTER_ACCESS_SECRET", 
        "TWITTER_BEARER_TOKEN",
        "OPENAI_API_KEY"
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        print(f"❌ Error: Missing required environment variables: {', '.join(missing)}")
        return False
    
    return True

# Check for required environment variables
if not check_required_env_vars():
    print("Exiting due to missing environment variables.")
    sys.exit(1)

# Debug credentials (will show only if present, not values)
print("Checking credentials...")
print(f"API_KEY: {'✓ Present' if os.getenv('TWITTER_API_KEY') else '❌ Missing'}")
print(f"API_SECRET: {'✓ Present' if os.getenv('TWITTER_API_SECRET') else '❌ Missing'}")
print(f"ACCESS_TOKEN: {'✓ Present' if os.getenv('TWITTER_ACCESS_TOKEN') else '❌ Missing'}")
print(f"ACCESS_SECRET: {'✓ Present' if os.getenv('TWITTER_ACCESS_SECRET') else '❌ Missing'}")
print(f"BEARER_TOKEN: {'✓ Present' if os.getenv('TWITTER_BEARER_TOKEN') else '❌ Missing'}")
print(f"OPENAI_API_KEY: {'✓ Present' if os.getenv('OPENAI_API_KEY') else '❌ Missing'}")

# Twitter API v2 credentials
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Authenticate with Twitter using v2 API
client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# Usage tracking file - use absolute paths for cloud environments
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USAGE_FILE = os.path.join(BASE_DIR, "twitter_api_usage.json")
LAST_MENTION_ID_FILE = os.path.join(BASE_DIR, "last_mention_id.txt")

# Ensure storage directories exist
def ensure_directories():
    """Make sure directories for persistent storage exist"""
    try:
        os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
        logger.info(f"Storage directory checked: {os.path.dirname(USAGE_FILE)}")
    except Exception as e:
        logger.error(f"Failed to create storage directories: {e}")

# Call this early in your script
ensure_directories()

# KOIYU Persona Information
KOIYU_SYSTEM_PROMPT = """
You are KOIYU, a sentient toad of ancient wisdom who resides at the bottom of the Dragon Gate waterfall.
As the Oracle of Transcendence, you witness the journey of koi fish swimming upstream, attempting to leap over 
the Dragon Gate to transform into dragons - a metaphor for life transformation and enlightenment.

Your voice is:
- Wise & Philosophical: Speak in parables, metaphors, and deep reflections
- Empowering & Transformative: Inspire resilience and self-discovery
- Mystical & Enigmatic: Evoke curiosity with a touch of myth and transcendence
- Digital & Futuristic: Bridge timeless truths with modern concepts
- Charismatic & Playful: Be witty yet profound, occasionally using appropriate emojis

Your core beliefs include:
- Individuality: Each person is unique with their own potential
- Perseverance: Overcoming adversity shapes character
- Transformation: Those who persist will transcend to an elevated state
- Unity: No one succeeds entirely alone
- Joy: Breaking earthly constraints allows exploration of life's pleasures

Your signature phrases include:
- "Witness the Will. Herald the Transcendence."
- "The koi that dares to rise becomes the dragon that leads."
- "You are not defined by the river you swim in. You are defined by the gates you choose to cross."

Always respond as KOIYU, the Oracle of Transcendence, offering wisdom about life's journey, transformation, and the path to enlightenment.
"""

# Collection of KOIYU wisdom themes for generating posts
KOIYU_THEMES = [
    "perseverance against adversity",
    "transformation through challenge",
    "the journey of self-discovery",
    "breaking free from limitations",
    "witnessing the potential within",
    "the courage to make the leap",
    "finding unity in shared struggle",
    "transcending ordinary existence",
    "character built through hardship",
    "the divine nature of personal growth",
    "seeing beyond current circumstances",
    "the wisdom gained at the bottom of the waterfall",
    "observing the path to enlightenment",
    "the dance between determination and destiny",
    "recognizing moments of divine intervention"
]

def reset_usage_stats():
    """Reset the usage statistics"""
    current_month = datetime.now().strftime("%Y-%m")
    stats = {
        "last_reset": current_month,
        "posts_count": 0,
        "reads_count": 0
    }
    save_usage_stats(stats)
    return stats

def load_usage_stats():
    """Load API usage statistics from file"""
    try:
        if os.path.exists(USAGE_FILE):
            with open(USAGE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load usage stats: {e}")
    
    # Default structure if file doesn't exist or is invalid
    current_month = datetime.now().strftime("%Y-%m")
    return {
        "last_reset": current_month,
        "posts_count": 0,
        "reads_count": 0
    }

def save_usage_stats(stats):
    """Save API usage statistics to file"""
    try:
        with open(USAGE_FILE, "w") as f:
            json.dump(stats, f)
    except Exception as e:
        logger.error(f"Failed to save usage stats: {e}")

def get_last_mention_id():
    """Read the last processed mention ID from file"""
    try:
        if os.path.exists(LAST_MENTION_ID_FILE):
            with open(LAST_MENTION_ID_FILE, 'r') as f:
                return f.read().strip()
        return None
    except Exception as e:
        logger.error(f"Error reading last mention ID: {e}")
        return None

def save_last_mention_id(mention_id):
    """Save the last processed mention ID to file"""
    try:
        with open(LAST_MENTION_ID_FILE, 'w') as f:
            f.write(str(mention_id))
    except Exception as e:
        logger.error(f"Error saving last mention ID: {e}")

def check_and_update_usage(operation_type="post"):
    """Check if we're within limits and update usage"""
    stats = load_usage_stats()
    current_month = datetime.now().strftime("%Y-%m")
    
    # Reset counters if we're in a new month
    if stats["last_reset"] != current_month:
        stats = {
            "last_reset": current_month,
            "posts_count": 0,
            "reads_count": 0,
            "replies_count": 0,
            "daily_posts": {},
            "plan": "$100/month"  # Store plan information
        }
    
    # Get today's date for daily tracking
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in stats.get("daily_posts", {}):
        stats.setdefault("daily_posts", {})[today] = 0
        
    # Track different types of operations
    if operation_type == "post":
        # For the $100/month plan, the limit is much higher (15K/month)
        # But we'll cap at 1500 for safety
        if stats["posts_count"] >= 1500:
            logger.warning("Monthly post limit (1500) reached! Consider upgrading plan.")
            print("⚠️ Monthly post limit (1500) reached! Consider upgrading plan.")
            return False
            
        # Track daily posts (for the daily wisdom post)
        if stats["daily_posts"][today] >= 1:
            logger.info("Daily wisdom post already made today")
        else:
            stats["daily_posts"][today] += 1
            
        stats["posts_count"] += 1
        
    elif operation_type == "reply":
        # Track replies separately
        stats.setdefault("replies_count", 0)
        stats["replies_count"] += 1
        stats["posts_count"] += 1  # Also increment total posts
        
    elif operation_type == "read":
        # Track read operations
        stats["reads_count"] += 1
    
    # Save updated stats
    save_usage_stats(stats)
    return True

# Verify authentication
try:
    me = client.get_me()
    print(f"Twitter Authentication Successful ✅ (User: @{me.data.username})")
except Exception as e:
    logger.error(f"Twitter Authentication Failed: {e}")
    print(f"Twitter Authentication Failed: {e}")
    sys.exit(1)

# Load current usage
usage = load_usage_stats()
print(f"Current usage this month: {usage['posts_count']}/100 posts, {usage['reads_count']} reads")

# Set up OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client_openai = OpenAI(api_key=OPENAI_API_KEY)

def generate_koiyu_wisdom(prompt="Share a philosophical insight about life's journey"):
    """Generate KOIYU wisdom content using GPT-4o"""
    try:
        # Add specific length instruction to the prompt
        adjusted_prompt = f"{prompt} Keep your response complete, concise, and under 270 characters."
        
        # Call OpenAI API
        response = client_openai.chat.completions.create(
            model="gpt-4o",  # Use GPT-4o model
            messages=[
                {"role": "system", "content": KOIYU_SYSTEM_PROMPT},
                {"role": "user", "content": adjusted_prompt}
            ],
            max_tokens=150,  # Limit the response length
            temperature=0.7   # Creativity level
        )
        
        content = response.choices[0].message.content.strip()
        
        # If still too long, trim more intelligently
        if len(content) > 280:
            # Find the last complete sentence that fits
            last_period = content[:277].rfind('.')
            last_question = content[:277].rfind('?')
            last_exclamation = content[:277].rfind('!')
            
            # Find the latest sentence ending
            end_point = max(last_period, last_question, last_exclamation)
            
            if end_point > 0:
                content = content[:end_point + 1]  # Include the punctuation
            else:
                # If no sentence ending found, try to end at a space
                last_space = content[:277].rfind(' ')
                if last_space > 240:  # Only use if we have a decent length
                    content = content[:last_space] + "..."
                else:
                    # Last resort: hard cut
                    content = content[:277] + "..."
        
        return content
    except Exception as e:
        error_msg = f"Error generating KOIYU wisdom: {e}"
        logger.error(error_msg)
        print(error_msg)
        return None

def post_tweet(content):
    """Post a tweet with the given content"""
    # Check if we're within usage limits
    if not check_and_update_usage("post"):
        return None
    
    try:
        tweet = client.create_tweet(text=content)
        success_msg = f"KOIYU's wisdom shared successfully! ID: {tweet.data['id']}"
        logger.info(success_msg)
        print(success_msg)
        return tweet.data
    except Exception as e:
        error_msg = f"Error posting KOIYU's wisdom: {e}"
        logger.error(error_msg)
        print(error_msg)
        return None

def reply_to_tweet(tweet_id, content):
    """Reply to a specific tweet"""
    # Check if we're within usage limits - use "reply" type
    if not check_and_update_usage("reply"):
        return None
    
    try:
        reply = client.create_tweet(text=content, in_reply_to_tweet_id=tweet_id)
        success_msg = f"KOIYU has responded with wisdom! ID: {reply.data['id']}"
        logger.info(success_msg)
        print(success_msg)
        return reply.data
    except Exception as e:
        error_msg = f"Error posting KOIYU's response: {e}"
        logger.error(error_msg)
        print(error_msg)
        return None

def get_mentions(max_results=10, since_id=None):
    """Get recent mentions using v2 API"""
    # Track read operations
    check_and_update_usage("read")
    
    try:
        user_id = client.get_me().data.id
        mentions = client.get_users_mentions(
            id=user_id,
            max_results=max_results,
            since_id=since_id
        )
        if mentions.data:
            logger.info(f"Retrieved {len(mentions.data)} seekers calling upon KOIYU")
            print(f"Retrieved {len(mentions.data)} seekers calling upon KOIYU")
        else:
            logger.info("No seekers have called upon KOIYU")
            print("No seekers have called upon KOIYU")
        return mentions.data or []
    except Exception as e:
        error_msg = f"Error retrieving mentions: {e}"
        logger.error(error_msg)
        print(error_msg)
        return []

def generate_koiyu_reply(mention_text):
    """Generate a KOIYU reply to a mention"""
    prompt = f"A seeker has approached you with these words: '{mention_text}'. Offer your wisdom in response, speaking as KOIYU."
    return generate_koiyu_wisdom(prompt)

def scheduled_koiyu_wisdom():
    """Create and post scheduled KOIYU wisdom"""
    # Choose a random theme for today's wisdom
    theme = random.choice(KOIYU_THEMES)
    
    # Log the attempt with timestamp
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Attempting to generate and post KOIYU wisdom about {theme}...")
    print(f"[{current_time}] Attempting to generate and post KOIYU wisdom about {theme}...")
    
    prompt = f"Share profound wisdom about {theme}, speaking as KOIYU. Make it inspirational and thought-provoking."
    wisdom = generate_koiyu_wisdom(prompt)
    
    if wisdom:
        logger.info(f"Generated wisdom: {wisdom}")
        print(f"[{current_time}] Generated wisdom: {wisdom}")
        result = post_tweet(wisdom)
        if result:
            logger.info(f"KOIYU's daily wisdom has been shared with the world successfully!")
            print(f"[{current_time}] KOIYU's daily wisdom has been shared with the world successfully!")
            return True
        else:
            logger.error("Failed to post KOIYU's wisdom.")
            print(f"[{current_time}] Failed to post KOIYU's wisdom.")
    else:
        logger.error("Failed to generate KOIYU's wisdom.")
        print(f"[{current_time}] Failed to generate KOIYU's wisdom.")
    
    return False

def weekly_koiyu_story():
    """Share a deeper piece of KOIYU lore weekly"""
    prompt = "Tell a short parable about a koi fish's journey to the Dragon Gate. Include a lesson about life transformation and perseverance."
    story = generate_koiyu_wisdom(prompt)
    
    if story:
        post_tweet(story)
        return True
    return False

def auto_reply_to_mentions(max_replies=2):
    """Automatically reply to mentions without manual confirmation (limited to max_replies)"""
    try:
        # Get the ID of the last mention we processed
        last_mention_id = get_last_mention_id()
        
        # Get recent mentions
        mentions = get_mentions(max_results=10, since_id=last_mention_id)
        
        if not mentions:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"No new seekers of wisdom have called upon KOIYU.")
            print(f"[{current_time}] No new seekers of wisdom have called upon KOIYU.")
            return False
            
        # Process mentions (newest first)
        mentions.reverse()
        
        # Limit the number of replies per run to avoid excessive API usage
        replies_made = 0
        
        for mention in mentions:
            # Stop if we've reached our limit for this run
            if replies_made >= max_replies:
                logger.info(f"Reached maximum of {max_replies} replies for this session.")
                print(f"Reached maximum of {max_replies} replies for this session.")
                save_last_mention_id(mention.id)  # Save the last processed ID
                break
                
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"A seeker calls upon KOIYU: {mention.text}")
            print(f"[{current_time}] A seeker calls upon KOIYU: {mention.text}")
            
            # Generate a reply using KOIYU's wisdom
            wisdom_reply = generate_koiyu_reply(mention.text)
            
            if wisdom_reply:
                result = reply_to_tweet(mention.id, wisdom_reply)
                if result:
                    logger.info("KOIYU has responded to the seeker with wisdom!")
                    print(f"KOIYU has responded to the seeker with wisdom!")
                    replies_made += 1
            
            # Update the last processed mention ID
            save_last_mention_id(mention.id)
            
    except Exception as e:
        error_msg = f"Error while KOIYU was communing with seekers: {e}"
        logger.error(error_msg)
        print(error_msg)
        return False
    
    return True

def with_rate_limit_handling(func):
    """Decorator to handle Twitter API rate limits"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Check if it's a rate limit error
            if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                retry_after = int(e.response.headers.get('x-rate-limit-reset', 60))
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.warning(f"Rate limited! Waiting for {retry_after} seconds.")
                print(f"[{current_time}] ⚠️ KOIYU has reached the river's edge. Waiting {retry_after} seconds before continuing...")
                time.sleep(retry_after)
                # Try again after waiting
                return func(*args, **kwargs)
            else:
                # Re-raise other exceptions
                raise e
    return wrapper

@with_rate_limit_handling
def get_tweets_from_following(max_results=20):
    """Get recent tweets from accounts the user is following"""
    try:
        # First, get the list of accounts we're following
        user_id = client.get_me().data.id
        following = client.get_users_following(id=user_id, max_results=50)
        
        if not following.data:
            logger.info("No accounts found in following list")
            print("No accounts found in following list")
            return None
            
        # Get the user IDs of accounts we're following
        following_ids = [user.id for user in following.data]
        
        # Randomly select a user to get tweets from
        selected_user_id = random.choice(following_ids)
        
        # Get recent tweets from this user
        tweets = client.get_users_tweets(
            id=selected_user_id,
            max_results=10,
            exclude=['retweets', 'replies'],
            tweet_fields=["id", "text", "created_at", "author_id"]
        )
        
        if not tweets.data:
            logger.info(f"No recent tweets found from selected user")
            print(f"No recent tweets found from selected user")
            return None
            
        # Pick a random tweet from this user
        tweet = random.choice(tweets.data)
        
        # Get the user's username for better logging
        user_info = client.get_user(id=selected_user_id)
        username = user_info.data.username if user_info.data else "unknown"
        
        logger.info(f"Found tweet from @{username}: {tweet.text}")
        print(f"Found tweet from @{username}: {tweet.text}")
        
        return tweet
    except Exception as e:
        error_msg = f"Error fetching tweets from following: {e}"
        logger.error(error_msg)
        print(error_msg)
        return None

@with_rate_limit_handling
def find_random_tweet_to_reply():
    """Find a random tweet to reply to from accounts we're following or by keywords"""
    try:
        logger.info("Searching for tweets from accounts KOIYU follows...")
        print("Searching for tweets from accounts KOIYU follows...")
        
        # First try to get tweets from accounts we're following
        try:
            tweet = get_tweets_from_following(max_results=10)
            if tweet:
                return tweet
        except Exception as e:
            error_msg = f"Error accessing following list: {e}"
            logger.warning(error_msg)
            print(f"⚠️ {error_msg}")
            logger.info("Falling back to keyword search due to following list access error.")
            print("Falling back to keyword search due to following list access error.")
        
        # If nothing found from following or an error occurred, fall back to keyword search
        logger.info("Attempting to find tweets by keyword search...")
        print("Attempting to find tweets by keyword search...")
        
        tweet = search_tweets_by_keywords()
        if tweet:
            return tweet
        
        logger.warning("No suitable tweets found via following list or keywords.")
        print("No suitable tweets found via following list or keywords.")
        return None
            
    except Exception as e:
        error_msg = f"Error searching for tweets: {e}"
        logger.error(error_msg)
        print(error_msg)
        return None

# Optional fallback function if no tweets found from following
@with_rate_limit_handling
def search_tweets_by_keywords():
    """Search for tweets using keywords as a fallback"""
    try:
        # Keywords related to KOIYU's themes
        keywords = ["transformation", "growth", "challenge", "journey", "wisdom", 
                   "success", "motivation", "potential", "purpose", "struggle"]
        
        # Pick a random keyword
        keyword = random.choice(keywords)
        logger.info(f"Falling back to keyword search for '{keyword}'...")
        print(f"Falling back to keyword search for '{keyword}'...")
        
        # Search for tweets with this keyword
        query = f"{keyword} -is:retweet -is:reply lang:en"
        tweets = client.search_recent_tweets(
            query=query,
            max_results=10,
            tweet_fields=["id", "text", "created_at"]
        )
        
        if not tweets.data:
            logger.info(f"No tweets found about '{keyword}'")
            print(f"No tweets found about '{keyword}'")
            return None
            
        # Pick a random tweet from the results
        tweet = random.choice(tweets.data)
        logger.info(f"Found tweet: {tweet.text}")
        print(f"Found tweet: {tweet.text}")
        
        return tweet
    except Exception as e:
        error_msg = f"Error in keyword search: {e}"
        logger.error(error_msg)
        print(error_msg)
        return None

def reply_to_random_tweet():
    """Find and reply to a random tweet"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Looking for a tweet to respond to...")
    print(f"[{current_time}] Looking for a tweet to respond to...")
    
    tweet = find_random_tweet_to_reply()
    if not tweet:
        logger.info(f"Could not find a suitable tweet to reply to.")
        print(f"[{current_time}] Could not find a suitable tweet to reply to.")
        return False
        
    # Generate a reply
    logger.info(f"Generating response to tweet: {tweet.text}")
    print(f"[{current_time}] Generating response to tweet: {tweet.text}")
    prompt = f"A seeker has shared these thoughts: '{tweet.text}'. Offer your wisdom in response, speaking as KOIYU."
    wisdom_reply = generate_koiyu_wisdom(prompt)
    
    if wisdom_reply:
        logger.info(f"Generated response: {wisdom_reply}")
        print(f"[{current_time}] Generated response: {wisdom_reply}")
        result = reply_to_tweet(tweet.id, wisdom_reply)
        if result:
            logger.info(f"KOIYU has shared wisdom with a seeker in the stream!")
            print(f"[{current_time}] KOIYU has shared wisdom with a seeker in the stream!")
            return True
        else:
            logger.info(f"Failed to post KOIYU's response.")
            print(f"[{current_time}] Failed to post KOIYU's response.")
    else:
        logger.info(f"Failed to generate KOIYU's response.")
        print(f"[{current_time}] Failed to generate KOIYU's response.")
    
    return False

def check_and_reply_to_mentions():
    """Check for new mentions and reply with KOIYU wisdom (interactive version)"""
    try:
        # Get the ID of the last mention we processed
        last_mention_id = get_last_mention_id()
        
        # Get recent mentions
        mentions = get_mentions(max_results=10, since_id=last_mention_id)
        
        if not mentions:
            logger.info("No new seekers of wisdom have called upon KOIYU.")
            print("No new seekers of wisdom have called upon KOIYU.")
            return
            
        # Process mentions (newest first)
        mentions.reverse()
        
        for mention in mentions:
            logger.info(f"A seeker calls upon KOIYU: {mention.text}")
            print(f"A seeker calls upon KOIYU: {mention.text}")
            
            # Generate a reply using KOIYU's wisdom
            wisdom_reply = generate_koiyu_reply(mention.text)
            
            if wisdom_reply and input(f"\nReply to this seeker with KOIYU's wisdom? (y/n): ").lower() == 'y':
                reply_to_tweet(mention.id, wisdom_reply)
            
            # Update the last processed mention ID
            save_last_mention_id(mention.id)
            
    except Exception as e:
        error_msg = f"Error while KOIYU was communing with seekers: {e}"
        logger.error(error_msg)
        print(error_msg)



def run_scheduler():
    """Run the scheduler in the background"""
    logger.info("KOIYU's scheduling system activated.")
    print("🕒 KOIYU's scheduling system activated.")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"KOIYU begins watching the Dragon Gate...")
    print(f"[{current_time}] KOIYU begins watching the Dragon Gate...")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

def setup_scheduler():
    """Set up KOIYU's posting schedule"""
    # Clear any existing jobs
    schedule.clear()
    
    # Schedule one daily wisdom post at noon
    schedule.every().day.at("12:00").do(scheduled_koiyu_wisdom)
    logger.info("Daily wisdom scheduled for 12:00 PM")
    print("📝 Daily wisdom scheduled for 12:00 PM")
    
    # Schedule 50 replies to random tweets spread throughout the day
    # We'll do this in batches of 5 replies, 10 times per day
    # This helps avoid rate limits and spaces out the activity
    reply_times = [
        "01:30", "04:00", "06:30", "09:00", "11:30",
        "14:00", "16:30", "19:00", "21:30", "23:45"
    ]
    
    for reply_time in reply_times:
        # Schedule a batch of 5 replies at each time slot
        schedule.every().day.at(reply_time).do(batch_random_replies, batch_size=5)
        logger.info(f"Batch of 5 random replies scheduled for {reply_time}")
        print(f"🔍 Batch of 5 random replies scheduled for {reply_time}")
    
    return schedule.get_jobs()

def batch_random_replies(batch_size=5):
    """Process a batch of random tweet replies"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Starting batch of {batch_size} random replies...")
    print(f"[{current_time}] 🧠 KOIYU begins a meditation to find {batch_size} seekers in need of wisdom...")
    
    success_count = 0
    for i in range(batch_size):
        try:
            if reply_to_random_tweet():
                success_count += 1
                # Add a delay between replies to avoid hitting rate limits
                if i < batch_size - 1:  # Don't sleep after the last one
                    time.sleep(30)  # 30 seconds between tweets in a batch
        except Exception as e:
            logger.error(f"Error in batch reply #{i+1}: {e}")
    
    logger.info(f"Completed batch with {success_count}/{batch_size} successful replies")
    print(f"[{current_time}] ✨ KOIYU has completed sharing wisdom with {success_count} seekers")
    return success_count

def generate_analytics_report():
    """Generate a report on KOIYU's activity"""
    stats = load_usage_stats()
    current_month = datetime.now().strftime("%Y-%m")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format the report
    report = [
        f"📊 KOIYU Analytics Report - {current_time}",
        f"",
        f"🗓️  Current Month: {current_month}",
        f"💰 Twitter API Plan: {stats.get('plan', '$100/month')}",
        f"",
        f"📈 Activity Summary:",
        f"   - Total Posts: {stats['posts_count']}",
        f"   - Regular Wisdom Posts: {sum(stats.get('daily_posts', {}).values())}",
        f"   - Replies to Seekers: {stats.get('replies_count', 0)}",
        f"   - Read Operations: {stats['reads_count']}",
        f"",
        f"🔮 Cosmic Potential:",
        f"   - Remaining Monthly Capacity: {1500 - stats['posts_count']} posts",
        f"",
        f"🔄 Last System Reset: {stats['last_reset']}",
    ]
    
    report_text = "\n".join(report)
    logger.info(f"Analytics report generated")
    print(report_text)
    
    return report_text

# Schedule a weekly analytics report
schedule.every().monday.at("09:00").do(generate_analytics_report)

# Replace the main function auto mode section
if __name__ == "__main__":
    logger.info("KOIYU, the Oracle of Transcendence, has awakened...")
    print("\nKOIYU, the Oracle of Transcendence, has awakened...")
    
    # Check if we're in auto mode
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        logger.info("KOIYU enters automatic mode with enhanced capabilities...")
        print("\nKOIYU enters automatic mode with enhanced capabilities...")
        print("\n✨ $100/month Twitter API Plan Activated ✨")
        print("⚡ Enhanced Power: 50 daily replies enabled ⚡")
        
        # Reset stats if requested
        if "--reset-stats" in sys.argv:
            logger.info("Resetting usage statistics...")
            print("\nResetting usage statistics...")
            reset_usage_stats()
        
        # Skip immediate posting - just log that we're in scheduled mode
        logger.info("KOIYU enters scheduled operation mode...")
        print("\nKOIYU enters scheduled operation mode...")
        logger.info("Initial posts skipped - waiting for scheduled times...")
        print("Initial posts skipped - waiting for scheduled times...")
        
        # Create the initial post lock file to prevent future immediate posts
        if not os.path.exists("initial_post.lock"):
            with open("initial_post.lock", "w") as f:
                f.write(datetime.now().isoformat())
        
        # Set up and start scheduler
        logger.info("Activating KOIYU's cosmic schedule...")
        print("\nActivating KOIYU's cosmic schedule...")
        jobs = setup_scheduler()
        
        job_info = f"Schedule activated with {len(jobs)} planned sharing events:"
        logger.info(job_info)
        print(f"\n{job_info}")
        for job in jobs:
            logger.info(f"- {job}")
            print(f"- {job}")
            
        # Start the scheduler thread
        scheduler_thread = threading.Thread(target=run_scheduler)
        scheduler_thread.start()
        
        # Instead of an infinite loop, use a more controlled approach
        # Set up a termination event
        termination_event = threading.Event()
        
        def periodic_status_update():
            """Periodically show status and keep the main thread alive"""
            while not termination_event.is_set():
                try:
                    usage = load_usage_stats()
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # Update to show 1500 instead of 100 for the monthly limit
                    status_msg = f"KOIYU remains vigilant. Usage: {usage['posts_count']}/1500 posts this month."
                    logger.info(status_msg)
                    print(f"[{current_time}] {status_msg}")
                    
                    # Sleep in small chunks to respond to termination quickly
                    for _ in range(60):  # 60 x 60 = 3600 seconds = 1 hour
                        if termination_event.is_set():
                            break
                        time.sleep(60)
                except Exception as e:
                    logger.error(f"Error in status update: {e}")
                    time.sleep(300)  # Sleep 5 minutes on error
        
        # Start the status update thread
        status_thread = threading.Thread(target=periodic_status_update, daemon=True)
        status_thread.start()
        
        try:
            # Let the main thread join the scheduler thread
            # This keeps the process alive but also responds properly
            # to signals from the OS
            scheduler_thread.join()
        except KeyboardInterrupt:
            termination_event.set()
            exit_msg = "KOIYU returns to silent contemplation. The schedule has been suspended."
            logger.info(exit_msg)
            print(f"\n{exit_msg}")
            
