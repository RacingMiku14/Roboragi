'''
AnimeBot.py
Acts as the "main" file and ties all the other functionality together.
'''

import praw
import re
import traceback
import requests
import time

import Search
import CommentBuilder
import DatabaseHandler
import Config

# --- Config Variables ---
USERNAME = ''
PASSWORD = ''
USERAGENT = ''
REDDITAPPID = ''
REDDITAPPSECRET = ''
#

try:
    import Config
    USERNAME = Config.username
    PASSWORD = Config.password
    USERAGENT = Config.useragent
    REDDITAPPID = Config.redditappid
    REDDITAPPSECRET = Config.redditappsecret
except ImportError:
    pass

reddit = praw.Reddit(USERAGENT)

#There's probably a better way to do this. Might move it to the backend database at some point
subredditlist = 'roboragi+amv+animebazaar+animecirclejerk+animedeals+animedubs+animefigures+animegifs+animehaiku+animeicons+animemashups+animemusic+animenews+animenocontext+animephonewallpapers+animeranks+animesketch+animesuggest+animethemes+animevectorwallpapers+animewallpaper+animeworldproblems+awwnime+bishounen+crunchyroll+ecchi+endcard+hentai+imouto+japaneseanimation+japaneseanimation+kemonomimi+kitsunemimi+manga+mangaswap+melanime+metaanime+moescape+nekomimi+nihilate+nsfwanimegifs+otaku+pantsu+patchuu+postyourmal+qualityanime+seinen+trueanime+vocaloid+waifu+watchinganime+weeaboo+weeabootales+yaoi+yuri+zettairyouiki'

#the subreddits where expanded requests are disabled
disableexpanded = ['animesuggest']

#Sets up Reddit for PRAW
def setupReddit():
    try:
        print('Getting Reddit access token')
        reddit.set_oauth_app_info(client_id=REDDITAPPID, client_secret=REDDITAPPSECRET, redirect_uri='http://127.0.0.1:65010/' 'authorize_callback')

        client_auth = requests.auth.HTTPBasicAuth(REDDITAPPID, REDDITAPPSECRET)
        post_data = {"grant_type": "password", "username": USERNAME, "password": PASSWORD}
        headers = {"User-Agent": USERAGENT}
        response = requests.post("https://www.reddit.com/api/v1/access_token", auth=client_auth, data=post_data, headers=headers)

        reddit.set_access_credentials(set(['identity', 'read', 'submit']), response.json()['access_token'])
        print('Access token set\n')
    except:
        print('Error with setting up Reddit')

#The main function
def start():
    print('Starting comment stream:')

    #This opens a constant stream of comments. It will loop until there's a major error (usually this means the Reddit access token needs refreshing)
    comment_stream = praw.helpers.comment_stream(reddit, subredditlist, limit=250, verbosity=0)

    for comment in comment_stream:

        #Is the comment valid (i.e. it's not made by Roboragi and I haven't seen it already). If no, try to add it to the "already seen pile" and skip to the next comment. If yes, keep going.
        if not (Search.isValidComment(comment, reddit)):
            try:
                if not (DatabaseHandler.commentExists(comment.id)):
                    DatabaseHandler.addComment(comment.id, comment.author.name, comment.subreddit, False)
            except:
                pass
            continue

        #Anime/Manga requests that are found go into separate arrays
        animeArray = []
        mangaArray = []

        #ignores all "code" markup (i.e. anything between backticks)
        comment.body = re.sub(r"\`(?s)(.*?)\`", "", comment.body)
        
        #This checks for requests. First up we check all known tags for the !stats request
        # Assumes tag begins and ends with a whitespace OR at the string beginning/end
        if re.search('(^|\s)({!stats}|{{!stats}}|<!stats>|<<!stats>>)($|\s|.)', comment.body, re.S) is not None:
            commentReply = CommentBuilder.buildStatsComment(comment.subreddit)
        else:
            
            #The basic algorithm here is:
            #If it's an expanded request, build a reply using the data in the braces, clear the arrays, add the reply to the relevant array and ignore everything else.
            #If it's a normal request, build a reply using the data in the braces, add the reply to the relevant array.


            #Counts the number of expanded results vs total results. If it's not just a single expanded result, they all get turned into normal requests.
            numOfRequest = 0
            numOfExpandedRequest = 0
            forceNormal = False

            for match in re.finditer("\{{2}([^}]*)\}{2}|\<{2}([^>]*)\>{2}", comment.body, re.S):
                numOfRequest += 1
                numOfExpandedRequest += 1
                
            for match in re.finditer("(?<=(?<!\{)\{)([^\{\}]*)(?=\}(?!\}))|(?<=(?<!\<)\<)([^\<\>]*)(?=\>(?!\>))", comment.body, re.S):
                numOfRequest += 1

            if (numOfExpandedRequest >= 1) and (numOfRequest > 1):
                forceNormal = True

            #Expanded Anime
            for match in re.finditer("\{{2}([^}]*)\}{2}", comment.body, re.S):
                reply = ''

                if (forceNormal) or (str(comment.subreddit).lower() in disableexpanded):
                    reply = Search.buildAnimeReply(match.group(1), False, comment)
                else:
                    reply = Search.buildAnimeReply(match.group(1), True, comment)                    

                if (reply is not None):
                    animeArray.append(reply)

            #Normal Anime  
            for match in re.finditer("(?<=(?<!\{)\{)([^\{\}]*)(?=\}(?!\}))", comment.body, re.S):
                reply = Search.buildAnimeReply(match.group(1), False, comment)
                
                if (reply is not None):
                    animeArray.append(reply)

            #Expanded Manga
            #NORMAL EXPANDED
            for match in re.finditer("\<{2}([^>]*)\>{2}(?!(:|\>))", comment.body, re.S):
                reply = ''
                
                if (forceNormal) or (str(comment.subreddit).lower() in disableexpanded):
                    reply = Search.buildMangaReply(match.group(1), False, comment)
                else:
                    reply = Search.buildMangaReply(match.group(1), True, comment)

                if (reply is not None):
                    mangaArray.append(reply)

            #AUTHOR SEARCH EXPANDED
            for match in re.finditer("\<{2}([^>]*)\>{2}:\(([^)]+)\)", comment.body, re.S):
                reply = ''
                
                if (forceNormal) or (str(comment.subreddit).lower() in disableexpanded):
                    reply = Search.buildMangaReplyWithAuthor(match.group(1), match.group(2), False, comment)
                else:
                    reply = Search.buildMangaReplyWithAuthor(match.group(1), match.group(2), True, comment)

                if (reply is not None):
                    mangaArray.append(reply)

            #Normal Manga
            #NORMAL
            for match in re.finditer("(?<=(?<!\<)\<)([^\<\>]+)\>(?!(:|\>))", comment.body, re.S):
                reply = Search.buildMangaReply(match.group(1), False, comment)

                if (reply is not None):
                    mangaArray.append(reply)

            #AUTHOR SEARCH
            for match in re.finditer("(?<=(?<!\<)\<)([^\<\>]*)\>:\(([^)]+)\)", comment.body, re.S):
                reply = Search.buildMangaReplyWithAuthor(match.group(1), match.group(2), False, comment)

                if (reply is not None):
                    mangaArray.append(reply)
                
            #Here is where we create the final reply to be posted

            #The final comment reply. We add stuff to this progressively.
            commentReply = ''

            #If we have anime AND manga in one reply we format stuff a little differently
            multipleTypes = False

            #Basically just to keep track of people posting the same title multiple times (e.g. {Nisekoi}{Nisekoi}{Nisekoi})
            postedAnimeTitles = []
            postedMangaTitles = []
            
            if (len(animeArray) > 0) and (len(mangaArray) > 0):
                multipleTypes = True
                commentReply += '**Anime**\n\n'

            #Adding all the anime to the final comment. If there's manga too we split up all the paragraphs and indent them in Reddit markup by adding a '>', then recombine them
            for i, animeReply in enumerate(animeArray):
                if not (i is 0):
                    commentReply += '\n\n'
                    
                if multipleTypes:
                    splitSections = re.split('\s{2,}',animeReply['comment'])
                    newSections = []
                    for section in splitSections:
                        newSections.append('>' + section)
                    animeReply['comment'] = '\n\n'.join(newSections)

                if not (animeReply['title'] in postedAnimeTitles):
                    postedAnimeTitles.append(animeReply['title'])
                    commentReply += animeReply['comment']
                

            if multipleTypes:
                commentReply += '\n\n**Manga**\n\n'

            #Adding all the manga to the final comment
            for i, mangaReply in enumerate(mangaArray):
                if not (i is 0):
                    commentReply += '\n\n'

                if multipleTypes:
                    splitSections = re.split('\s{2,}',mangaReply['comment'])
                    newSections = []
                    for section in splitSections:
                        newSections.append('>' + section)
                    mangaReply['comment'] = '\n\n'.join(newSections)
                
                if not (mangaReply['title'] in postedMangaTitles):
                    postedMangaTitles.append(mangaReply['title'])
                    commentReply += mangaReply['comment']

            #If there are more than 10 requests, shorten them all 
            if not (commentReply is '') and (len(animeArray) + len(mangaArray) >= 10):
                commentReply = re.sub(r"\^\((.*?)\)", "", commentReply, flags=re.M)

        #If there was actually something found, add the signature and post the comment to Reddit. Then, add the comment to the "already seen" database.
        if not (commentReply is ''):
            commentReply += '\n\n---\n\n^[FAQ](http://www.reddit.com/r/Roboragi/wiki/index) ^| ^[/r/](http://www.reddit.com/r/Roboragi/) ^| [^Edit](https://www.reddit.com/r/Roboragi/comments/3i82q0/by_mentioning_his_username_roboragi_can_now) ^| ^[Mistake?](http://www.reddit.com/r/Roboragi/submit?selftext=true&title=[ISSUE]&text=https://www.reddit.com/r/manga/comments/3knp2l/looking_for_a_manga/cuyxqxz) ^| ^[Source](https://github.com/Nihilate/Roboragi) ^| ^(New:) [^Available ^Reddit-wide](https://www.reddit.com/r/Roboragi/comments/3ke553/announcement_roboragi_can_be_used_nearly_anywhere) ^+ [^author ^search ^for ^manga](https://www.reddit.com/r/Roboragi/comments/3kntf8/announcement_for_more_accurate_manga_results_you/)'
            
            try:
                comment.reply(commentReply)
                print("Comment made.\n")

                try:
                    DatabaseHandler.addComment(comment.id, comment.author.name, comment.subreddit, True)
                except:
                    traceback.print_exc()
            except:
                traceback.print_exc()
        else:
            try:
                DatabaseHandler.addComment(comment.id, comment.author.name, comment.subreddit, False)
            except:
                traceback.print_exc()


# ------------------------------------#
#Here's the stuff that actually gets run

#Initialise Reddit.
setupReddit()

#Loop the comment stream until the Reddit access token expires. Then get a new access token and start the stream again.
while 1:
    try:        
        start()
    except Exception as e:
        #traceback.print_exc()

        setupReddit()
