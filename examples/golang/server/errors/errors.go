package errors

type CodeErrInterface interface {
	Code() int
	Error() string
	Message() string
}

type Error struct {
	code    int
	message string
}

func New(code int, message string) *Error {
	return &Error{
		code:    code,
		message: message,
	}
}

func (e Error) Code() int {
	return e.code
}

func (e Error) Error() string {
	return e.Message()
}

func (e Error) Message() string {
	return e.message
}
