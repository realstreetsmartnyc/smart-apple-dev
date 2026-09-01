module {{NAME}}

go 1.21

# Firebase Go SDK dependencies
# Install with: go get firebase.google.com/go/v4

# Required imports
require (
    firebase.google.com/go/v4 1.13.0
    # Optionally add specific Firebase products:
    # firebase.google.com/go/v4/auth 1.13.0
    # firebase.google.com/go/v4/firestore 1.13.0
    # firebase.google.com/go/v4/storage 1.13.0
    # firebase.google.com/go/v4/messaging 1.13.0
)

# Basic Go module configuration
go 1.21