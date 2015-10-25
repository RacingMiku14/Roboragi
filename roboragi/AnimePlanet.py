from pyquery import PyQuery as pq
import requests
import difflib
import traceback
import pprint
import collections

BASE_URL = "http://www.anime-planet.com"

def sanitiseSearchText(searchText):
    return searchText.replace('(TV}', 'TV')

def getAnimeURL(searchText):
    try:
        searchText = sanitiseSearchText(searchText)
        
        html = requests.get(BASE_URL + "/anime/all?name=" + searchText.replace(" ", "%20"))
        ap = pq(html.text)

        animeList = []

        #If it's taken us to the search page
        if ap.find('.pillFilters.pure-g'):
            for entry in ap.find('.card.entry.pure-u-1-6'):
                entryTitle = pq(entry).find('a').text()
                entryURL = pq(entry).find('a').attr('href')
                
                anime = {}
                anime['title'] = entryTitle
                anime['url'] = BASE_URL + entryURL
                animeList.append(anime)

            closestName = difflib.get_close_matches(searchText.lower(), [x['title'].lower() for x in animeList], 1, 0.85)[0]
            closestURL = ''
            
            for anime in animeList:
                if anime['title'].lower() == closestName:
                    return anime['url']
            
        #Else if it's taken us right to the series page, get the url from the meta tag
        else:
            return ap.find("meta[property='og:url']").attr('content')
        return None
            
    except:
        #traceback.print_exc()
        return None

#Probably doesn't need to be split into two functions given how similar they are, but it might be worth keeping separate for the sake of issues between anime/manga down the line
def getMangaURL(searchText, authorName=None):
    try:
        if authorName:
            html = requests.get(BASE_URL + "/manga/all?name=" + searchText.replace(" ", "%20") + '&author=' + authorName.replace(" ", "%20"))

            if "No results found" in html.text:
                rearrangedAuthorNames = collections.deque(authorName.split(' '))
                rearrangedAuthorNames.rotate(-1)
                rearrangedName = ' '.join(rearrangedAuthorNames)
                html = requests.get(BASE_URL + "/manga/all?name=" + searchText.replace(" ", "%20") + '&author=' + rearrangedName.replace(" ", "%20"))
            
        else:
            html = requests.get(BASE_URL + "/manga/all?name=" + searchText.replace(" ", "%20"))
            
        ap = pq(html.text)

        mangaList = []

        #If it's taken us to the search page
        if ap.find('.pillFilters.pure-g'):
            for entry in ap.find('.card.entry.pure-u-1-6'):
                entryTitle = pq(entry).find('a').text()
                entryURL = pq(entry).find('a').attr('href')
                
                manga = {}
                manga['title'] = entryTitle
                manga['url'] = BASE_URL + entryURL
                mangaList.append(manga)

            if authorName:
                authorName = authorName.lower()
                authorName = authorName.split(' ')

                for manga in mangaList:
                    manga['title'] = manga['title'].lower()
                    
                    for name in authorName:
                        manga['title'] = manga['title'].replace(name, '')
                    manga['title'] = manga['title'].replace('(', '').replace(')', '').strip()
                
            closestName = difflib.get_close_matches(searchText.lower(), [x['title'].lower() for x in mangaList], 1, 0.85)[0]
            closestURL = ''
            
            for manga in mangaList:
                if manga['title'].lower() == closestName:
                    return manga['url']
            
        #Else if it's taken us right to the series page, get the url from the meta tag
        else:
            return ap.find("meta[property='og:url']").attr('content')
        return None
            
    except:
        #traceback.print_exc()
        return None