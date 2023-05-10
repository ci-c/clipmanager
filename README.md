# clipmanager

sqlite clipmanager on python

## Commands
 
Command  

### `store`
STDIN: data
STDOUT: -

### `pick`
STDIN: id
STDOUT: - 

### `get-data`
STDIN: id
STDOUT: data 

### `get-time`
STDIN: id
STDOUT: time in ISO
### `get-list`
STDIN: -
STDOUT: data
    separator: `\n` 
### `restore`
STDIN: -
STDOUT: - 
### `get-last`
STDIN: number
STDOUT: id 

### `remove`
STDIN: id
STDOUT: log 
### `clear`
STDIN: -
STDOUT: - 