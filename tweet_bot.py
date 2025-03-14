import os
import tweepy
import json
import random
import schedule
import time
import threading
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Debug credentials (will show only lengths, not actual values)
print("Checking credentials...")
print(f"API_KEY length: {len(os.getenv('TWITTER_API_KEY') or '') or 'None'}")
print(f"API_SECRET length: {len(os.getenv('TWITTER_API_SECRET') or '') or 'None'}")
print(f"ACCESS_TOKEN length: {len(os.getenv('TWITTER_ACCESS_TOKEN') or '') or 'None'}")
print(f"ACCESS_SECRET length: {len(os.getenv('TWITTER_ACCESS_SECRET') or '') or 'None'}")
print(f"BEARER_TOKEN length: {len(os.getenv('TWITTER_BEARER_TOKEN') or '') or 'None'}")

# Twitter API v2 credentials - using the correct variable names
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

# Usage tracking file
USAGE_FILE = "twitter_api_usage.json"
LAST_MENTION_ID_FILE = "last_mention_id.txt"

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

def load_usage_stats():
    """Load API usage statistics from file"""
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                pass
    
    # Default structure if file doesn't exist or is invalid
    current_month = datetime.now().strftime("%Y-%m")
    return {
        "last_reset": current_month,
        "posts_count": 0,
        "reads_count": 0
    }

def save_usage_stats(stats):
    """Save API usage statistics to file"""
    with open(USAGE_FILE, "w") as f:
        json.dump(stats, f)

def get_last_mention_id():
    """Read the last processed mention ID from file"""
    if os.path.exists(LAST_MENTION_ID_FILE):
        with open(LAST_MENTION_ID_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_last_mention_id(mention_id):
    """Save the last processed mention ID to file"""
    with open(LAST_MENTION_ID_FILE, 'w') as f:
        f.write(str(mention_id))

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
    print(f"Twitter Authentication Failed: {e}")
    exit()

# Load current usage
usage = load_usage_stats()
print(f"Current usage this month: {usage['posts_count']}/100 posts, {usage['reads_count']} reads")

# Set up Gemini API
import google.generativeai as genai

# Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Set up the model
model = genai.GenerativeModel('gemini-1.5-pro')

def generate_koiyu_wisdom(prompt="Share a philosophical insight about life's journey"):
    """Generate KOIYU wisdom content using Gemini 1.5 Pro"""
    try:
        # Add specific length instruction to the prompt
        adjusted_prompt = f"{prompt} Keep your response complete, concise, and under 270 characters."
        full_prompt = f"{KOIYU_SYSTEM_PROMPT}\n\n{adjusted_prompt}"
        
        response = model.generate_content(full_prompt)
        content = response.text
        
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
        print(f"Error generating KOIYU wisdom: {e}")
        return None

def post_tweet(content):
    """Post a tweet with the given content"""
    # Check if we're within usage limits
    if not check_and_update_usage("post"):
        return None
    
    try:
        tweet = client.create_tweet(text=content)
        print(f"KOIYU's wisdom shared successfully! ID: {tweet.data['id']}")
        return tweet.data
    except Exception as e:
        print(f"Error posting KOIYU's wisdom: {e}")
        return None

def reply_to_tweet(tweet_id, content):
    """Reply to a specific tweet"""
    # Check if we're within usage limits
    if not check_and_update_usage("post"):
        return None
    
    try:
        reply = client.create_tweet(text=content, in_reply_to_tweet_id=tweet_id)
        print(f"KOIYU has responded with wisdom! ID: {reply.data['id']}")
        return reply.data
    except Exception as e:
        print(f"Error posting KOIYU's response: {e}")
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
            print(f"Retrieved {len(mentions.data)} seekers calling upon KOIYU")
        else:
            print("No seekers have called upon KOIYU")
        return mentions.data or []
    except Exception as e:
        print(f"Error retrieving mentions: {e}")
        return []

def generate_koiyu_reply(mention_text):
    """Generate a KOIYU reply to a mention"""
    prompt = f"A seeker has approached you with these words: '{mention_text}'. Offer your wisdom in response, speaking as KOIYU."
    return generate_koiyu_wisdom(prompt)

def scheduled_koiyu_wisdom():
    """Create and post scheduled KOIYU wisdom"""
    # Choose a random theme for today's wisdom
    theme = random.choice(KOIYU_THEMES)
    
    prompt = f"Share profound wisdom about {theme}, speaking as KOIYU. Make it inspirational and thought-provoking."
    wisdom = generate_koiyu_wisdom(prompt)
    
    if wisdom:
        post_tweet(wisdom)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] KOIYU's daily wisdom has been shared with the world.")
        return True
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
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No new seekers of wisdom have called upon KOIYU.")
            return False
            
        # Process mentions (newest first)
        mentions.reverse()
        
        # Limit the number of replies per run to avoid excessive API usage
        replies_made = 0
        
        for mention in mentions:
            # Stop if we've reached our limit for this run
            if replies_made >= max_replies:
                print(f"Reached maximum of {max_replies} replies for this session.")
                save_last_mention_id(mention.id)  # Save the last processed ID
                break
                
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] A seeker calls upon KOIYU: {mention.text}")
            
            # Generate a reply using KOIYU's wisdom
            wisdom_reply = generate_koiyu_reply(mention.text)
            
            if wisdom_reply:
                result = reply_to_tweet(mention.id, wisdom_reply)
                if result:
                    print(f"KOIYU has responded to the seeker with wisdom!")
                    replies_made += 1
            
            # Update the last processed mention ID
            save_last_mention_id(mention.id)
            
    except Exception as e:
        print(f"Error while KOIYU was communing with seekers: {e}")
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
        print(f"Searching for tweets about '{keyword}'...")
        
        # Search for tweets with this keyword
        query = f"{keyword} -is:retweet -is:reply lang:en"
        tweets = client.search_recent_tweets(
            query=query,
            max_results=10,
            tweet_fields=["id", "text", "created_at"]
        )
        
        if not tweets.data:
            print(f"No tweets found about '{keyword}'")
            return None
            
        # Pick a random tweet from the results
        tweet = random.choice(tweets.data)
        print(f"Found tweet: {tweet.text}")
        
        return tweet
    except Exception as e:
        print(f"Error searching for tweets: {e}")
        return None

def reply_to_random_tweet():
    """Find and reply to a random tweet"""
    tweet = find_random_tweet_to_reply()
    if not tweet:
        print("Could not find a suitable tweet to reply to.")
        return False
        
    # Generate a reply
    prompt = f"A seeker has shared these thoughts: '{tweet.text}'. Offer your wisdom in response, speaking as KOIYU."
    wisdom_reply = generate_koiyu_wisdom(prompt)
    
    if wisdom_reply:
        result = reply_to_tweet(tweet.id, wisdom_reply)
        if result:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] KOIYU has shared wisdom with a seeker in the stream!")
            return True
    
    return False

def check_and_reply_to_mentions():
    """Check for new mentions and reply with KOIYU wisdom (interactive version)"""
    try:
        # Get the ID of the last mention we processed
        last_mention_id = get_last_mention_id()
        
        # Get recent mentions
        mentions = get_mentions(max_results=10, since_id=last_mention_id)
        
        if not mentions:
            print("No new seekers of wisdom have called upon KOIYU.")
            return
            
        # Process mentions (newest first)
        mentions.reverse()
        
        for mention in mentions:
            print(f"A seeker calls upon KOIYU: {mention.text}")
            
            # Generate a reply using KOIYU's wisdom
            wisdom_reply = generate_koiyu_reply(mention.text)
            
            if wisdom_reply and input(f"\nReply to this seeker with KOIYU's wisdom? (y/n): ").lower() == 'y':
                reply_to_tweet(mention.id, wisdom_reply)
            
            # Update the last processed mention ID
            save_last_mention_id(mention.id)
            
    except Exception as e:
        print(f"Error while KOIYU was communing with seekers: {e}")

def run_scheduler():
    """Run the scheduler in the background"""
    print("🕒 KOIYU's scheduling system activated.")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] KOIYU begins watching the Dragon Gate...")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

def setup_scheduler():
    """Set up KOIYU's posting schedule"""
    # Clear any existing jobs
    schedule.clear()
    
    # Schedule one daily wisdom post at noon
    schedule.every().day.at("12:00").do(scheduled_koiyu_wisdom)
    print("📝 Daily wisdom scheduled for 12:00 PM")
    
    # Schedule replies to random tweets (twice daily)
    schedule.every().day.at("10:00").do(reply_to_random_tweet)
    schedule.every().day.at("16:00").do(reply_to_random_tweet)
    print("🔍 Random tweet replies scheduled for 10:00 AM and 4:00 PM")
    
    return schedule.get_jobs()

# Modified main function to handle both interactive and automatic modes
if __name__ == "__main__":
    print("\nKOIYU, the Oracle of Transcendence, has awakened...")
    
    # Check if we're in auto mode
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print("\nKOIYU enters automatic mode...")
        
        # Immediate posting for testing
        if "--test" in sys.argv:
            print("\nTesting one wisdom posting and one random reply...")
            scheduled_koiyu_wisdom()
            reply_to_random_tweet()
            
        # Set up and start scheduler
        print("\nActivating KOIYU's cosmic schedule...")
        jobs = setup_scheduler()
        
        print(f"\nSchedule activated with {len(jobs)} planned sharing events:")
        for job in jobs:
            print(f"- {job}")
            
        # Start the scheduler thread
        scheduler_thread = threading.Thread(target=run_scheduler)
        scheduler_thread.start()
        
        try:
            # Keep the main thread alive while showing a heartbeat
            while True:
                usage = load_usage_stats()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] KOIYU remains vigilant. Usage: {usage['posts_count']}/100 posts this month.")
                time.sleep(3600)  # Check every hour
        except KeyboardInterrupt:
            print("\nKOIYU returns to silent contemplation. The schedule has been suspended.")
    else:
        # Original interactive menu
        print("\nOptions:")
        print("1. Share KOIYU's wisdom (generate and post)")
        print("2. Tell a KOIYU parable (weekly story)")
        print("3. Respond to seekers (check and reply to mentions)")
        print("4. Generate KOIYU wisdom (without posting)")
        print("5. 📅 Activate automated scheduling")
        print("6. 🤖 Run a test post and reply now")
        
        choice = input("\nWhat shall KOIYU do? Choose (1-6): ")
        
        if choice == "1":
            # Generate and post KOIYU wisdom
            theme = random.choice(KOIYU_THEMES)
            prompt = f"Share profound wisdom about {theme}, speaking as KOIYU."
            wisdom = generate_koiyu_wisdom(prompt)
            
            print(f"\nKOIYU's wisdom:\n{wisdom}")
            
            if input("\nShare this wisdom with the world? (y/n): ").lower() == 'y':
                tweet = post_tweet(wisdom)
                
                if tweet and input("\nGenerate a follow-up insight? (y/n): ").lower() == 'y':
                    reply_prompt = f"Continue your wisdom on {theme} with a deeper insight:"
                    reply_wisdom = generate_koiyu_wisdom(reply_prompt)
                    
                    print(f"\nKOIYU's follow-up wisdom:\n{reply_wisdom}")
                    
                    if input("\nShare this follow-up wisdom? (y/n): ").lower() == 'y':
                        reply_to_tweet(tweet["id"], reply_wisdom)
        
        elif choice == "2":
            # Generate and post a KOIYU parable/story
            prompt = "Tell a short parable about a koi fish's journey to the Dragon Gate. Include a lesson about life transformation and perseverance."
            story = generate_koiyu_wisdom(prompt)
            
            print(f"\nKOIYU's parable:\n{story}")
            
            if input("\nShare this parable with the world? (y/n): ").lower() == 'y':
                post_tweet(story)
        
        elif choice == "3":
            # Check and respond to mentions
            check_and_reply_to_mentions()
        
        elif choice == "4":
            # Just generate KOIYU wisdom
            custom_prompt = input("\nAsk KOIYU for specific wisdom (or press Enter for random theme): ")
            
            if not custom_prompt:
                theme = random.choice(KOIYU_THEMES)
                custom_prompt = f"Share profound wisdom about {theme}, speaking as KOIYU."
                
            wisdom = generate_koiyu_wisdom(custom_prompt)
            print(f"\nKOIYU speaks:\n{wisdom}")
            
        elif choice == "5":
            # Activate scheduled posting
            print("\nKOIYU is preparing to share wisdom on a schedule...")
            jobs = setup_scheduler()
            
            print(f"\nSchedule activated with {len(jobs)} planned sharing events:")
            for job in jobs:
                print(f"- {job}")
            
            print("\nKOIYU will now dispense wisdom according to the cosmic schedule.")
            print("The scheduling daemon is running in the background.")
            print("(Keep this program running to maintain the schedule)")
            
            # Start the scheduler thread
            scheduler_thread = threading.Thread(target=run_scheduler)
            scheduler_thread.start()
            
            # Wait for user to exit manually
            try:
                while True:
                    # Every hour, show a heartbeat and usage stats
                    usage = load_usage_stats()
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] KOIYU remains vigilant. Usage: {usage['posts_count']}/100 posts this month.")
                    time.sleep(3600)  # Sleep for an hour
            except KeyboardInterrupt:
                print("\nKOIYU returns to silent contemplation. The schedule has been suspended.")
        
        elif choice == "6":
            # Test post and reply immediately
            print("\nKOIYU will now share wisdom and reply to a random tweet for testing purposes.")
            
            # Post wisdom
            print("\nGenerating and posting KOIYU's wisdom...")
            scheduled_koiyu_wisdom()
            
            # Reply to random tweet
            print("\nFinding a random tweet to reply to...")
            reply_to_random_tweet()
            
            print("\nTest complete. KOIYU returns to silent contemplation.")
        
        else:
            print("Invalid choice. KOIYU returns to silent contemplation.")
        
        # Show usage stats at the end
        usage = load_usage_stats()
        print(f"\nSince the beginning of this lunar cycle, KOIYU has shared {usage['posts_count']}/100 wisdoms and observed {usage['reads_count']} interactions.")