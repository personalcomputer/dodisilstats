#!/usr/bin/env python
import requests
import sys
import os
import os.path
import datetime
#from bs4 import BeautifulSoup
import sqlite3
import lxml.html
from lxml.cssselect import CSSSelector
import re
from nltk.stem.wordnet import WordNetLemmatizer
import nltk

isil_pr_blog_url = 'http://www.defense.gov/home/features/2014/0814_iraq/Airstrikes6.html'
cache_name = 'cache.html'

database_name = 'airstrikes.db'

units = {'zero': 0, #used for NLP #cardinal numbers or (some) determiners
'no': 0,
'one': 1,
'another': 1,
'the': 1,
'an': 1,
'a': 1,
'two': 2,
'three': 3,
'four': 4,
'five': 5,
'six': 6,
'seven': 7,
'eight': 8,
'nine': 9,
'ten': 10,
'eleven': 11,
'twelve': 12,
'thirteen': 13,
'fourteen': 14,
'fifteen': 15}

#The following 'should_be_adjectives' is a kludge for helping to identify entire noun phrases, including noun adjuncts etc.
should_be_adjectives = ['fighting', 'logistics', 'security', 'supply', 'support', 'ied', 'personnel', 'mortar', 'launching', 'machine', 'production', 'command', 'and', 'control', 'armed', 'staging', 'oil', 'firing', 'training', 'air', 'ammunition', 'warfare', 'observation', 'jamming', 'crude', 'oil', 'collection', 'artillery']
should_be_stop_nouns = ['humvee', 'hmmwv', 'hmmwvs', 'other']
status_verbs = ['destroyed', 'damaged', 'struck', 'suppressed', 'damaging',  'destroying', 'targeted', 'stuck'] #regarding 'stuck' - DoD made a typo

lemmatizer = WordNetLemmatizer()

def get_isil_pr_liveblog():
  try:
    cache_time = datetime.datetime.fromtimestamp(os.path.getmtime(cache_name))
    if (datetime.datetime.now() - cache_time).total_seconds()/(60*60) < 6: #cache fresh within 6 hours
      return open(cache_name).read()
  except OSError:
    pass

  r = requests.get(isil_pr_blog_url)
  html = r.text

  cachefile = open(cache_name, 'w')
  cachefile.write(html.encode('utf8'))
  cachefile.close()

  return html

def get_entries(html):
  #soup = BeautifulSoup(html, 'html.parser')
  #soup.ul
  tree = lxml.html.fromstring(html)
  results = CSSSelector('ul.entries > li')(tree)

  return results


class SentenceWithContext(object):
  def __init__(self, sentence, country, date_start, date_end):
    self.sentence = sentence
    self.country = country
    self.date_start = date_start
    self.date_end = date_end

class AirStrike(object):
  def __init__(self, dod_identification, status, country, near, date_start, date_end, debug_source):
    self.dod_identification = dod_identification
    self.status = status
    self.country = country
    self.near = near
    self.date_start = date_start
    self.date_end = date_end
    self.debug_source = debug_source

def parse_target_sentence(sentence):
  sentence.sentence = sentence.sentence.strip()
  stext = sentence.sentence

  #ignore junk sentences:
  if 'All aircraft' in stext and 'safely' in stext:
    return []
  if 'Airstrike assessments are based on initial reports' in stext:
    return []
  if re.match('To conduct these (air)?strikes, the U.S. employed', stext):
    return []
  if re.match('In addition, .+ (also )?participated', stext):
    return []


  airstrikes = []

  tagged = nltk.pos_tag(nltk.word_tokenize(stext))


  #The below section is very bad sentence parsing code. It roughly splits sentences into sets of subject-verbs while disqualifying any pairs that involve aistrikes or uses a verb not in the pre-selected acceptable status_verbs ("damaged", "destroyed", "struck", etc).
  #It does this job  in a very poor, extremely inefficient, and simply broken style. This was my first time playing with NLP and it suffices for the situation.
  #To rewrite, iterate over the tags only once, identifying noun-phrases, status verbs, and the 'was/were' flag in one go (using nltk.regexpparser as well as a of common noun-phrases that are parsed incorrectly), THEN follow a logic tree based on their recorded order to assemble the Airstrike entries. This will still falsly ignore some of the unusual phrases used in the original material, but will pick up 95%+ of the entries.
  #To understand the current code, if necassary, it is basically the above except the logic tree is intermixed in the iterating and instead of recording the orders it simply repetively iterates all over the sentence for every single potential entry.
  for i,w in enumerate(tagged):
    if w[1] in ['CD', 'DT']:
      #Number identified
      number = w[0].lower()
      if number in ['those', 'these', 'all', 'this']: #these words are not used in reference to # of targets killed and if they were they would be hard to parse because of the needed contextual knowledge
        continue
      try:
        number = int(number)
      except ValueError:
        number = units[number]

      #Identify status
      status = ''
      for nw in reversed(tagged[:i]):
        next_word = nw[0].lower()
        if (next_word in status_verbs):
          status = next_word
          if status == 'damaging':
            status = 'damaged'
          if status == 'destroying':
            status = 'destroyed'
          break

      #Identify target
      target = ''
      for ni, nw in list(enumerate(tagged))[i+1:]:
        next_word = nw[0].lower()
        if ((nw[1] in ['JJ', 'NNP']) and (next_word not in should_be_stop_nouns)) or (next_word in should_be_adjectives):
          target += next_word+' '
        elif nw[1].startswith('NN'):
          if re.match('(air)?strikes?', next_word):
            break

          try:
            if tagged[ni+1] in ['was', 'were'] or tagged[ni+2] in ['was', 'were']: #set intersection
              #uh oh, reset status
              for nnw in tagged[ni+2:]:
                nnext_word = nnw[0].lower()
                if (nnext_word in status_verbs):
                  status = nnext_word
                  break
          except IndexError:
            pass

          if next_word in ['others', 'other', 'another']:
            target = airstrikes[-1].dod_identification
          else:
            target += lemmatizer.lemmatize(next_word)

          if('mosul dam' in target or 'Bayji' in target or 'u.s.' in target):
            break

          if(not status):
            break

          print(status+': '+str(number)+'x '+target)
          airstrikes.extend(number*[AirStrike(target, status, sentence.country, 'unknown loc', sentence.date_start, sentence.date_end, stext)])
          break



  #'Near ([^,]+), ([^ ]+) airstrikes? (?:struck|destroyed) (.+)'

  #re.split('(?: and|, )', target_line)
  # '([^ ]+) (.+) '
  return airstrikes

def strip_invalid_sentences(sentences):
  fixed = []
  for sentence in sentences:
    sentence.sentence = sentence.sentence.strip()
    if sentence.sentence:
      fixed.append(sentence)

  return fixed

def split_sentences(sentences_text):
  sentences_text = sentences_text.replace('U.S.', '#USA')
  sentences = [s.replace('#USA', 'U.S.') for s in sentences_text.split('.')]

  return sentences

nildate = datetime.datetime.now()

def parse_entry(li):
  li_tostring = lxml.html.tostring(li, method='html', encoding='unicode')
  entry_parsed = []

  targets_sentences = []

  could_parse = False

  ###Parse Style 1
  #Test for sentence organization style 1
  style1_indicator = '''<p><strong>Syria</strong><br.?.?>\s*(</p>\s*)?<ul>\s*<li>-'''
  if re.search(style1_indicator, li_tostring) != None:
    states_list = CSSSelector('ul')(li)
    syria_list = states_list[0]
    iraq_list = states_list[1]
    if len(states_list) > 2: #one entry has anomalous 2 sections for iraq
      iraq_list.extend(states_list[2])

    syria_targets_sentences = [lxml.html.tostring(sentence, method='text', encoding='unicode')[2:] for sentence in CSSSelector('li')(syria_list)]
    iraq_targets_sentences = [lxml.html.tostring(sentence, method='text', encoding='unicode')[2:] for sentence in CSSSelector('li')(iraq_list)]

    targets_sentences.extend([SentenceWithContext(s, 'Syria', nildate, nildate) for s in syria_targets_sentences])
    targets_sentences.extend([SentenceWithContext(s, 'Iraq',  nildate, nildate) for s in  iraq_targets_sentences])

    could_parse = True

  ###Parse Style 2
  #Test for sentence organization style 2
  style2_indicator = '''<p>In Syria, '''
  if li_tostring.find(style2_indicator) != -1:
    syria_targets_sentences = []
    iraq_targets_sentences = []

    paragraphs_list = CSSSelector('p')(li)
    for paragraph in paragraphs_list:
      paragraph_text = lxml.html.tostring(paragraph, method='text', encoding='unicode')
      if paragraph_text.startswith('In Syria'):
        syria_targets_sentences.extend(split_sentences(paragraph_text))
      elif paragraph_text.startswith('In Iraq') or paragraph_text.startswith('Near Tal Afar'):
        iraq_targets_sentences.extend(split_sentences(paragraph_text))

    targets_sentences.extend([SentenceWithContext(s, 'Syria', nildate, nildate) for s in syria_targets_sentences])
    targets_sentences.extend([SentenceWithContext(s, 'Iraq',  nildate, nildate) for s in  iraq_targets_sentences])

    could_parse = True

  if not could_parse:
    date_note = ''
    try:
      date_element = CSSSelector('.date')(li)[0]
      date = lxml.html.tostring(date_element, method='text', encoding='unicode').strip()
      if date == 'Operational Summary:':
        raise Exception()
      date_note = ' dated '+date
    except:
      pass
    print('FAILED TO PARSE: 1 journal entry'+date_note+'. (could not identify as any known journal entry organization style)')# \n'+li_tostring)

  targets_sentences = strip_invalid_sentences(targets_sentences)

  airstrikes = []
  for sentence in targets_sentences:
    airstrikes.extend(parse_target_sentence(sentence))

  return airstrikes

def main():
  args = sys.argv

  #Get and parse press releases
  airstrikes = []

  html = get_isil_pr_liveblog()
  for entry in get_entries(html):
    airstrikes.extend(parse_entry(entry))


  #Write to DB
  #delete db (when it exists)
  try:
    os.remove(database_name)
  except OSError:
    pass

  conn = sqlite3.connect(database_name)
  c = conn.cursor()
  c.execute('CREATE TABLE targets (dod_identification TEXT, status TEXT, country TEXT, near TEXT, date_start TEXT, date_end TEXT, source TEXT)')
  conn.commit()

  for airstrike in airstrikes:
    c.execute("INSERT INTO targets VALUES (?,?,?,?,?,?,?)", (airstrike.dod_identification, airstrike.status, airstrike.country, airstrike.near, airstrike.date_start, airstrike.date_end, airstrike.debug_source))
  conn.commit()
  conn.close()

if __name__ == '__main__':
  main()
