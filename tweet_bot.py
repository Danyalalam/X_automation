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
            "reads_count": 0
        }
    
    if operation_type == "post":
        # Check if we're within the post limit (100 per month)
        if stats["posts_count"] >= 100:
            logger.warning("Monthly post limit (100) reached! Can't post until next month.")
            print("❌ Monthly post limit (100) reached! Can't post until next month.")
            return False
        stats["posts_count"] += 1
    elif operation_type == "read":
        # Track read operations (not critical as limit is higher)
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
    # Check if we're within usage limits
    if not check_and_update_usage("post"):
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

def find_random_tweet_to_reply():
    """Find a random tweet to reply to based on keywords"""
    try:
        # Keywords related to KOIYU's themes
        keywords = ["transformation", "growth", "challenge", "journey", "wisdom", 
                   "success", "motivation", "potential", "purpose", "struggle"]
        
        # Pick a random keyword
        keyword = random.choice(keywords)
        logger.info(f"Searching for tweets about '{keyword}'...")
        print(f"Searching for tweets about '{keyword}'...")
        
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
        error_msg = f"Error searching for tweets: {e}"
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
    
    # Schedule replies to random tweets (twice daily)
    schedule.every().day.at("10:00").do(reply_to_random_tweet)
    schedule.every().day.at("16:00").do(reply_to_random_tweet)
    logger.info("Random tweet replies scheduled for 10:00 AM and 4:00 PM")
    print("🔍 Random tweet replies scheduled for 10:00 AM and 4:00 PM")
    
    return schedule.get_jobs()

# Replace the main function auto mode section
if __name__ == "__main__":
    logger.info("KOIYU, the Oracle of Transcendence, has awakened...")
    print("\nKOIYU, the Oracle of Transcendence, has awakened...")
    
    # Check if we're in auto mode
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        logger.info("KOIYU enters automatic mode...")
        print("\nKOIYU enters automatic mode...")
        
        # Reset stats if requested
        if "--reset-stats" in sys.argv:
            logger.info("Resetting usage statistics...")
            print("\nResetting usage statistics...")
            reset_usage_stats()
        
        # Post immediately when first deployed
        if not os.path.exists("initial_post.lock"):
            logger.info("KOIYU will share initial wisdom with the world...")
            print("\nKOIYU will share initial wisdom with the world...")
            if scheduled_koiyu_wisdom():
                # Create a lock file to prevent initial posting on restart
                with open("initial_post.lock", "w") as f:
                    f.write(datetime.now().isoformat())
            
            # Wait a minute before attempting the random reply
            time.sleep(60)
            logger.info("KOIYU seeks a conversation to join...")
            print("\nKOIYU seeks a conversation to join...")
            reply_to_random_tweet()
        else:
            logger.info("Initial post already made. Skipping immediate post.")
            print("\nInitial post already made. Skipping immediate post.")
        
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
                    status_msg = f"KOIYU remains vigilant. Usage: {usage['posts_count']}/100 posts this month."
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
            
