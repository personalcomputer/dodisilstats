#!/usr/bin/env python
import sqlite3
import sys
import pandas as pd
import matplotlib.pyplot as plt
#from ggplot import * #Extremely undeveloped and broken port. Do not use.

database_name = '../airstrikes.db'

def usage():
  print('Usage: '+sys.argv[0]+' OUTPUT_PNG_FILE')

def main():
  args = sys.argv[1:]

  output_filename = ''

  try:
    output_filename = args[0]
  except IndexError:
    usage()
    sys.exit(1)

  conn = sqlite3.connect(database_name)
  targets = pd.read_sql('SELECT * FROM targets', conn)
  conn.close()

  g = targets.groupby('dod_identification')['dod_identification']
  targets_distribution_unfiltered = pd.DataFrame({'count': g.size()}).sort(['count'])


  targets_distribution_unfiltered.plot(kind='bar', figsize=(40, 40))
  plt.savefig(output_filename)


  '''gg = ggplot(aes(x='factor(dod_identification)', color='dod_identification'), data=targets) +\
      geom_bar() +\
      xlab("Targets") +\
      ylab("Count") +\
      labs(title="Distribution of identified (unfiltered DoD identifications) airstrike targets")
  ggsave(output_filename, gg)'''

  print('wrote out: '+output_filename)

if __name__ == '__main__':
  main()