dodisilstats
============
Automatically generated visualizations of the DoD's anti-ISIL air campaign press releases using natural language parsing.

###Usage:

Generate raw airstrike database from press releases (writes to airstrikes.db):
```
./gen.py
````

Create graph of targets destroyed and damaged after generating the database:
```
cd vis; ./targets-graph.py targets-graph.png
```

###Depends:
*note: install untested.*

````
requests sqlite3 lxml cssselect nltk
````
