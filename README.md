![license](https://img.shields.io/github/license/ci-c/clipmanager?style=flat-square)
![GitHub top language](https://img.shields.io/github/languages/top/ci-c/clipmanager?style=flat-square)
# clipmanager

sqlite clipmanager on python

## Usage  

### `store`

- STDIN: data
- STDOUT: -

### `pick`
- STDIN: id
- STDOUT: - 

### `get-list`
- STDIN: -
- STDOUT: data
  - separator: `\n` 
### `restore`
- STDIN: -
- STDOUT: - 

### `remove`
- STDIN: id
- STDOUT: log 
### `clear`
- STDIN: -
- STDOUT: - 