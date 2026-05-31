package account

import (
	shared "example.com/project/golang/server/views/routes/legacy/account"
	wailstransport "example.com/project/golang/server/views/transports/wailsv3"
)

func NewService(dispatcher wailstransport.EventDispatcher) *AccountService {
	return newGeneratedAccountService(shared.NewRouter(), dispatcher)
}
