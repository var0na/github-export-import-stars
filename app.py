import argparse
import logging
import os
import time
import json

from dotenv import load_dotenv
from github import Auth, Github, RateLimitExceededException

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
  level=logging.DEBUG,
  format='%(asctime)s - %(levelname)s - %(message)s',
  datefmt='%Y-%m-%d %H:%M:%S',
  filename='debug.log',
  filemode='a'
)
logger = logging.getLogger(__name__)

# Add a stream handler for console output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Add debug logging for tokens after logger setup
logger.debug(f"Export token from env: {os.getenv('GITHUB_EXPORT_TOKEN')[:5] if os.getenv('GITHUB_EXPORT_TOKEN') else 'Not set'}...")
logger.debug(f"Import token from env: {os.getenv('GITHUB_IMPORT_TOKEN')[:5] if os.getenv('GITHUB_IMPORT_TOKEN') else 'Not set'}...")


def github_login(user_token):
  auth1 = Auth.Token(user_token)
  g_con = Github(auth=auth1, per_page=100)
  try: # Verify authentication for both tokens
    try:
      g_user = g_con.get_user()
      g_user.login  # This will raise an exception if the token is invalid
      logger.info(f"Successfully authenticated export token for user: {g_user.login}")
    except Exception as e:
      logger.error(f"Failed to authenticate export token: {str(e)}")
      return
  except Exception as e:
    logger.error(f"An unexpected error occurred: {str(e)}")
    return None
  return g_con, g_user

def github_get_stars(github_user):
  g_user_stars = list(github_user.get_starred())
  logger.info(f"Found {len(g_user_stars)} starred repositories for export user")
  return g_user_stars

def compare_github_stars(github_user_stars1,github_user_stars2):
  repos_to_star = [repo for repo in github_user_stars1 if repo not in github_user_stars2]
  logger.info(f"Found {len(repos_to_star)} repositories to star")
  return repos_to_star

def stars_to_txt(github_user_stars, path="stars.txt"):
  with open(path, "w") as f:
    for star in github_user_stars:
      f.write(f"{star.svn_url}\n")
  logger.info(f"Exported list of {len(github_user_stars)} stars to '{path}'")

def github_import_stars(github_user, github_connection, github_user_stars):
  for star in github_user_stars:
    try:
      github_user.add_to_starred(github_connection.get_repo(star.full_name))
      logger.info(f"Starred {star.full_name}")
    except RateLimitExceededException as e:
      reset_time = e.headers.get('x-ratelimit-reset')
      retry_after = e.headers.get('retry-after')
      if retry_after:
        sleep_time = int(retry_after)
      elif reset_time:
        sleep_time = int(reset_time) - int(time.time())
      else:
        sleep_time = 60
      logger.warning(f"Rate limit exceeded. Retrying in {sleep_time} seconds.")
      time.sleep(sleep_time)
    except Exception as e:
      logger.error(f"Failed to star {star.full_name}: {str(e)}")
    time.sleep(1)

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Star GitHub repositories from one account to another.")
  parser.add_argument("--export-token", help="Access token for the account to export stars from")
  parser.add_argument("--import-token", help="Access token for the account to import stars to")
  parser.add_argument("--run", action="store_true", help="Actually star repositories (default is dry run)")
  args = parser.parse_args()

  logger.debug("Script started with arguments: %s", args)

  export_token = args.export_token or os.getenv('GITHUB_EXPORT_TOKEN')
  import_token = args.import_token or os.getenv('GITHUB_IMPORT_TOKEN')

  logger.debug(f"Export token: {'Set' if export_token else 'Not set'}")
  logger.debug(f"Import token: {'Set' if import_token else 'Not set'}")

  logger.debug(f"Export token starts with: {export_token[:5] if export_token else 'N/A'}...")
  logger.debug(f"Import token starts with: {import_token[:5] if import_token else 'N/A'}...")

  if export_token.startswith('ghp_'):
    try:
      connection, g_user = github_login(export_token)
      g_user_stars = github_get_stars(g_user)
      stars_to_txt(g_user_stars)
    except Exception as e:
      logger.error(f"An unexpected error occurred: {str(e)}")
    finally:
      connection.close()
      logger.debug("Closed Github connections")
  else:
    logger.error(f"Invalid token format. Ensure your tokens start with 'ghp_' and are correctly set in the .env file or provided as arguments.")
    logger.debug(f"Export token prefix: {export_token[:5] if export_token else 'N/A'}")
    exit(1)

  if import_token.startswith('ghp_') and export_token.startswith('ghp_') and False: # Not tested
    try:
      exp_connection, exp_g_user = github_login(export_token)
      imp_connection, imp_g_user = github_login(import_token)
      stars_list = compare_github_stars(github_get_stars(exp_g_user),github_get_stars(imp_g_user))
      github_import_stars(imp_g_user, imp_connection, stars_list)
    except Exception as e:
      logger.error(f"An unexpected error occurred: {str(e)}")
    finally:
      exp_connection.close()
      imp_connection.close()
      logger.debug("Closed Github connections")
  elif False:
    logger.error(f"Invalid token format. Ensure your tokens start with 'ghp_' and are correctly set in the .env file or provided as arguments.")
    logger.debug(f"Import token prefix: {import_token[:5] if import_token else 'N/A'}")
    exit(1)

  logger.debug("Script completed")
