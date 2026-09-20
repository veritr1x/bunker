// Adapted from cmd/lunar-tear/grpc.go at upstream 63df7d7.
package mobile

import (
	"google.golang.org/grpc"
	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/service"
	"lunar-tear/server/internal/store"
	"net"
	"strconv"
)

func registerServices(
	srv *grpc.Server,
	publicAddr string,
	octoURL string,
	authURL string,
	masterPath string,
	userStore interface {
		store.UserRepository
		store.SessionRepository
	},
	holder *runtime.Holder,
	noRegister bool,
) {
	pubHost, pubPortStr, _ := net.SplitHostPort(publicAddr)
	pubPort, _ := strconv.Atoi(pubPortStr)

	pb.RegisterBannerServiceServer(srv, service.NewBannerServiceServer(holder))
	pb.RegisterUserServiceServer(srv, service.NewUserServiceServer(userStore, userStore, holder, authURL, noRegister))
	pb.RegisterBattleServiceServer(srv, service.NewBattleServiceServer(userStore, userStore))
	pb.RegisterConfigServiceServer(srv, service.NewConfigServiceServer(pubHost, int32(pubPort), octoURL))
	pb.RegisterDataServiceServer(srv, service.NewDataServiceServerWithMasterPath(userStore, userStore, masterPath))
	pb.RegisterTutorialServiceServer(srv, service.NewTutorialServiceServer(userStore, userStore, holder))
	pb.RegisterGachaServiceServer(srv, service.NewGachaServiceServer(userStore, userStore, holder))
	pb.RegisterGiftServiceServer(srv, service.NewGiftServiceServer(userStore, userStore))
	pb.RegisterGamePlayServiceServer(srv, service.NewGameplayServiceServer())
	pb.RegisterGimmickServiceServer(srv, service.NewGimmickServiceServer(userStore, userStore, holder))
	pb.RegisterQuestServiceServer(srv, service.NewQuestServiceServer(userStore, userStore, holder))
	pb.RegisterNotificationServiceServer(srv, service.NewNotificationServiceServer(userStore, userStore))
	pb.RegisterCageOrnamentServiceServer(srv, service.NewCageOrnamentServiceServer(userStore, userStore, holder))
	pb.RegisterDeckServiceServer(srv, service.NewDeckServiceServer(userStore, userStore))
	pb.RegisterFriendServiceServer(srv, service.NewFriendServiceServer(userStore, userStore))
	pb.RegisterLoginBonusServiceServer(srv, service.NewLoginBonusServiceServer(userStore, userStore, holder))
	pb.RegisterNaviCutInServiceServer(srv, service.NewNaviCutInServiceServer(userStore, userStore))
	pb.RegisterContentsStoryServiceServer(srv, service.NewContentsStoryServiceServer(userStore, userStore))
	pb.RegisterDokanServiceServer(srv, service.NewDokanServiceServer(userStore, userStore))
	pb.RegisterPortalCageServiceServer(srv, service.NewPortalCageServiceServer(userStore, userStore))
	pb.RegisterCharacterViewerServiceServer(srv, service.NewCharacterViewerServiceServer(userStore, userStore, holder))
	pb.RegisterMissionServiceServer(srv, service.NewMissionServiceServer(userStore, userStore))
	pb.RegisterShopServiceServer(srv, service.NewShopServiceServer(userStore, userStore, holder))
	pb.RegisterCostumeServiceServer(srv, service.NewCostumeServiceServer(userStore, userStore, holder))
	pb.RegisterMovieServiceServer(srv, service.NewMovieServiceServer(userStore, userStore))
	pb.RegisterOmikujiServiceServer(srv, service.NewOmikujiServiceServer(userStore, userStore, holder))
	pb.RegisterWeaponServiceServer(srv, service.NewWeaponServiceServer(userStore, userStore, holder))
	pb.RegisterExploreServiceServer(srv, service.NewExploreServiceServer(userStore, userStore, holder))
	pb.RegisterCharacterBoardServiceServer(srv, service.NewCharacterBoardServiceServer(userStore, userStore, holder))
	pb.RegisterPartsServiceServer(srv, service.NewPartsServiceServer(userStore, userStore, holder))
	pb.RegisterCharacterServiceServer(srv, service.NewCharacterServiceServer(userStore, userStore, holder))
	pb.RegisterCompanionServiceServer(srv, service.NewCompanionServiceServer(userStore, userStore, holder))
	pb.RegisterMaterialServiceServer(srv, service.NewMaterialServiceServer(userStore, userStore, holder))
	pb.RegisterConsumableItemServiceServer(srv, service.NewConsumableItemServiceServer(userStore, userStore, holder))
	pb.RegisterSideStoryQuestServiceServer(srv, service.NewSideStoryQuestServiceServer(userStore, userStore, holder))
	pb.RegisterBigHuntServiceServer(srv, service.NewBigHuntServiceServer(userStore, userStore, holder))
	pb.RegisterRewardServiceServer(srv, service.NewRewardServiceServer(userStore, userStore, holder))
	pb.RegisterLabyrinthServiceServer(srv, service.NewLabyrinthServiceServer(userStore, userStore, holder))
}
