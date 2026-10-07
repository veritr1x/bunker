package service

// Friends offline: there are no other players, so the friend list stays empty
// and these actions succeed without changing anything, instead of failing as
// unknown calls.

import (
	"context"
	"log"

	pb "lunar-tear/server/gen/proto"

	emptypb "google.golang.org/protobuf/types/known/emptypb"
)

func (s *FriendServiceServer) SendFriendRequest(_ context.Context, req *pb.SendFriendRequestRequest) (*pb.SendFriendRequestResponse, error) {
	log.Printf("[FriendService] SendFriendRequest: no other players offline")
	return &pb.SendFriendRequestResponse{}, nil
}

func (s *FriendServiceServer) AcceptFriendRequest(context.Context, *pb.AcceptFriendRequestRequest) (*pb.AcceptFriendRequestResponse, error) {
	return &pb.AcceptFriendRequestResponse{}, nil
}

func (s *FriendServiceServer) DeclineFriendRequest(context.Context, *pb.DeclineFriendRequestRequest) (*pb.DeclineFriendRequestResponse, error) {
	return &pb.DeclineFriendRequestResponse{}, nil
}

func (s *FriendServiceServer) DeleteFriend(context.Context, *pb.DeleteFriendRequest) (*pb.DeleteFriendResponse, error) {
	return &pb.DeleteFriendResponse{}, nil
}

func (s *FriendServiceServer) CheerFriend(context.Context, *pb.CheerFriendRequest) (*pb.CheerFriendResponse, error) {
	return &pb.CheerFriendResponse{}, nil
}

func (s *FriendServiceServer) BulkCheerFriend(context.Context, *emptypb.Empty) (*pb.BulkCheerFriendResponse, error) {
	return &pb.BulkCheerFriendResponse{PlayerId: []int64{}}, nil
}

func (s *FriendServiceServer) ReceiveCheer(context.Context, *pb.ReceiveCheerRequest) (*pb.ReceiveCheerResponse, error) {
	return &pb.ReceiveCheerResponse{}, nil
}

func (s *FriendServiceServer) BulkReceiveCheer(context.Context, *emptypb.Empty) (*pb.BulkReceiveCheerResponse, error) {
	return &pb.BulkReceiveCheerResponse{PlayerId: []int64{}}, nil
}
