#!/bin/bash

rm -f airstrikes.db

sqlite3 airstrikes.db < database_init.sql